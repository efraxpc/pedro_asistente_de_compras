"""Porta de publicação independente do agente gerador."""
from difflib import SequenceMatcher

from .business import comparar
from .catalog import Cenario, buscar, ofertas
from .contracts import Alternativa, RespostaCompra


def verificar(resposta: RespostaCompra, cenario: Cenario, *, indice=None,
              observacoes: list[tuple[str, dict]] | None = None) -> list[str]:
    erros = []
    if resposta.dataset_id != cenario.dataset_id:
        return ["dataset alheio"]
    if resposta.estado == "esclarecimento":
        ambiguo = bool(resposta.solicitacao.produto and
                       len(buscar(cenario, resposta.solicitacao.produto, 2)) > 1)
        return [] if resposta.solicitacao.faltantes() or ambiguo else ["esclarecimento injustificado"]
    if resposta.estado == "sem_evidencia":
        return []
    if resposta.estado == "catalogo":
        consultas = [dado for nome, dado in (observacoes or [])
                     if nome == "consultar_catalogo" and dado.get("modo") == "sql"]
        if not consultas:
            return ["consulta ao catálogo não observada"]
        ultima = consultas[-1]
        if ultima.get("dataset_id") != cenario.dataset_id:
            return ["dataset alheio"]
        return [] if ultima.get("estado") in ("ok", "sem_linhas") else ["consulta rejeitada"]
    if resposta.estado == "preferencia":
        salva = any(nome == "salvar_preferencia" and dado.get("estado") == "ok"
                    for nome, dado in (observacoes or []))
        return [] if salva else ["preferência não salva"]
    if resposta.estado == "cep":
        cep = resposta.solicitacao.cep
        if not cep or not resposta.cidade or not resposta.uf or not resposta.modo_cep:
            return ["localização incompleta"]
        fontes = [e for e in resposta.evidencias if e.tipo == "viacep"
                  and e.fonte_id == f"ViaCEP:{cep}"]
        if not fontes:
            return ["falta evidência ViaCEP"]
        if not any(nome == "consultar_cep" and dado.get("estado") == "ok" and
                   dado.get("cep") == cep and dado.get("cidade") == resposta.cidade and
                   dado.get("uf") == resposta.uf and dado.get("modo") == resposta.modo_cep
                   for nome, dado in (observacoes or [])):
            return ["localização não coincide com o ViaCEP"]
        return []
    if resposta.estado == "politica":
        if indice is None or not resposta.mensagem.strip():
            return ["política sem índice ou afirmação"]
        fontes = [e for e in resposta.evidencias if e.tipo == "politica" and e.fonte_id]
        if not fontes:
            return ["política sem evidência"]
        for evidencia in fontes:
            doc = indice.docstore.search(evidencia.fonte_id)
            if not hasattr(doc, "page_content") or not evidencia.texto or evidencia.texto not in doc.page_content:
                erros.append(f"fragmento não corresponde: {evidencia.fonte_id}")
        if observacoes is not None:
            recuperados = {
                fragmento.get("fonte_id"): fragmento.get("texto", "")
                for nome, dado in observacoes if nome == "consultar_politicas"
                for fragmento in dado.get("fragmentos", [])
                if isinstance(fragmento, dict)
            }
            if not recuperados:
                erros.append("política sem recuperação observada")
            for evidencia in fontes:
                if evidencia.texto not in recuperados.get(evidencia.fonte_id, ""):
                    erros.append(f"fonte não recuperada: {evidencia.fonte_id}")
        return erros
    if resposta.solicitacao.faltantes() or not resposta.produto_id:
        return ["solicitação incompleta"]
    if resposta.produto_id != resposta.solicitacao.produto_id:
        erros.append("produto incoerente")
    oficiais = ofertas(cenario, resposta.produto_id)
    esperadas = comparar(resposta.solicitacao, oficiais)
    por_id = {a.oferta.id: a for a in esperadas}
    atuais = {a.oferta.id: a for a in resposta.alternativas}
    if not oficiais or len(atuais) != len(resposta.alternativas) or set(atuais) != set(por_id):
        erros.append("ofertas incompletas")
    for oid, alternativa in atuais.items():
        if oid not in por_id or alternativa != por_id[oid]:
            erros.append(f"alternativa incoerente: {oid}")
    fontes = {e.fonte_id for e in resposta.evidencias
              if e.tipo == "catalogo" and e.dataset_id == cenario.dataset_id}
    if set(por_id) - fontes:
        erros.append("evidência incompleta")
    validas = [a for a in esperadas if a.atende]
    if resposta.estado == "recomendacao":
        if not validas:
            erros.append("não existe oferta válida")
        elif (resposta.fornecedor_id != validas[0].oferta.fornecedor_id or
              resposta.total_centavos != validas[0].total_centavos):
            erros.append("vencedor ou total incorreto")
    elif resposta.estado == "sem_oferta" and validas:
        erros.append("existe, sim, oferta válida")
    return erros


COBERTURA_MINIMA_CITACAO = 0.8
COMPRIMENTO_MINIMO_CITACAO = 20


def ancorar_citacao(citacao: str, fragmento: str) -> tuple[str | None, float]:
    """Localiza no fragmento o trecho literal que corresponde a uma citação quase literal.

    Devolve o trecho copiado do fragmento e a cobertura da citação (0 a 1). O texto
    devolvido vem sempre do fragmento, nunca da citação.
    """
    citacao = " ".join(citacao.split())
    if len(citacao) < COMPRIMENTO_MINIMO_CITACAO or not fragmento:
        return None, 0.0
    blocos = [b for b in SequenceMatcher(None, fragmento, citacao, autojunk=False)
              .get_matching_blocks() if b.size >= 4]
    cobertura = sum(b.size for b in blocos) / len(citacao)
    if not blocos or cobertura < COBERTURA_MINIMA_CITACAO:
        return None, cobertura
    trecho = fragmento[blocos[0].a:blocos[-1].a + blocos[-1].size]
    if len(trecho) > 1.5 * len(citacao) + 20:
        return None, cobertura
    return trecho, cobertura


def ancorar_citacoes(resposta: RespostaCompra,
                     observacoes: list[tuple[str, dict]] | None) -> list[dict]:
    """Substitui cada citação de política pelo texto literal do fragmento recuperado.

    O modelo propõe qual fonte sustenta a resposta; o texto da evidência é posto pelo
    sistema. Uma citação que não pode ser ancorada fica intacta e será rejeitada por `verificar`.
    """
    recuperados = {
        fragmento.get("fonte_id"): fragmento.get("texto", "")
        for nome, dado in (observacoes or []) if nome == "consultar_politicas"
        for fragmento in dado.get("fragmentos", []) if isinstance(fragmento, dict)
    }
    relatorio = []
    for evidencia in resposta.evidencias:
        if evidencia.tipo != "politica":
            continue
        fragmento = recuperados.get(evidencia.fonte_id, "")
        if not fragmento:
            estado, cobertura = "fonte_nao_recuperada", 0.0
        elif evidencia.texto and evidencia.texto in fragmento:
            estado, cobertura = "literal", 1.0
        elif not evidencia.texto.strip():
            evidencia.texto, estado, cobertura = fragmento, "por_identificador", 1.0
        else:
            trecho, cobertura = ancorar_citacao(evidencia.texto, fragmento)
            if trecho is None:
                estado = "rejeitada"
            else:
                evidencia.texto, estado = trecho, "reancorada"
        relatorio.append({"fonte_id": evidencia.fonte_id, "estado": estado,
                          "cobertura": round(cobertura, 3)})
    return relatorio


def ancorar_cep(resposta: RespostaCompra, observacoes: list[tuple[str, dict]] | None,
                dataset_id: str) -> dict | None:
    """Preenche uma resposta de CEP com o que o ViaCEP devolveu neste turno.

    O modelo decide que a resposta é um CEP; cidade, estado, modo e evidência são postos
    pelo sistema a partir da observação da ferramenta. Sem uma observação válida a
    resposta fica intacta e será rejeitada por `verificar`.
    """
    if resposta.estado != "cep":
        return None
    validas = [dado for nome, dado in (observacoes or [])
               if nome == "consultar_cep" and dado.get("estado") == "ok"]
    pedido = resposta.solicitacao.cep
    dado = next((d for d in validas if d.get("cep") == pedido), None)
    if dado is None and not pedido and len({d.get("cep") for d in validas}) == 1:
        dado = validas[0]
    if dado is None:
        return {"estado": "sem_observacao_valida", "cep": pedido}
    from .contracts import Evidencia
    resposta.solicitacao.cep = dado["cep"]
    resposta.cidade, resposta.uf, resposta.modo_cep = dado["cidade"], dado["uf"], dado["modo"]
    resposta.evidencias = [Evidencia(tipo="viacep", fonte_id=f"ViaCEP:{dado['cep']}",
                                     texto=f"{dado['cidade']}/{dado['uf']}")]
    # Uma resposta de CEP não usa dados do catálogo: o cenário é definido pelo sistema.
    resposta.dataset_id = dataset_id
    return {"estado": "ancorada", "cep": dado["cep"]}


CAMPOS_SOLICITACAO = ("produto_id", "quantidade", "orcamento_centavos", "prazo_max_dias")
# O que o sistema acrescenta à solicitação e o modelo não precisa repetir.
CAMPOS_DO_SISTEMA = ("origem_preferida",)


def ancorar_recomendacao(resposta: RespostaCompra,
                         observacoes: list[tuple[str, dict]] | None) -> dict | None:
    """Substitui os números de uma comparação pelos que `comparar_ofertas` calculou.

    O modelo decide que a resposta é a comparação de uma solicitação; o vencedor, o total,
    as alternativas e as evidências são postos pelo sistema com o resultado da ferramenta
    para essa mesma solicitação. Se a ferramenta não foi chamada com essa solicitação, nada
    é alterado e a verificação exata decide.
    """
    if resposta.estado not in ("recomendacao", "sem_oferta"):
        return None
    pedido = tuple(getattr(resposta.solicitacao, campo) for campo in CAMPOS_SOLICITACAO)
    for nome, dado in reversed(observacoes or []):
        if nome != "comparar_ofertas":
            continue
        try:
            calculada = RespostaCompra.model_validate(dado)
        except ValueError:
            continue
        if tuple(getattr(calculada.solicitacao, campo) for campo in CAMPOS_SOLICITACAO) != pedido:
            continue
        mudancas = [campo for campo in ("estado", "fornecedor_id", "total_centavos", "alternativas")
                    if getattr(resposta, campo) != getattr(calculada, campo)]
        for campo in ("estado", "dataset_id", "produto_id", "fornecedor_id", "total_centavos",
                      "alternativas", "evidencias"):
            setattr(resposta, campo, getattr(calculada, campo))
        for campo in CAMPOS_DO_SISTEMA:
            setattr(resposta.solicitacao, campo, getattr(calculada.solicitacao, campo))
        return {"estado": "ancorada", "campos_corrigidos": mudancas}
    return {"estado": "sem_calculo_para_essa_solicitacao"}


LINHAS_VISIVEIS = 10


def ancorar_catalogo(resposta: RespostaCompra,
                     observacoes: list[tuple[str, dict]] | None) -> dict | None:
    """Redige uma resposta de catálogo com as linhas que a consulta SQL devolveu.

    O modelo decide que a resposta é uma consulta ao catálogo; a tabela, a contagem e a
    consulta executada são postas pelo sistema. Nenhum número é escrito pelo modelo.
    """
    if resposta.estado != "catalogo":
        return None
    consulta = next((dado for nome, dado in reversed(observacoes or [])
                     if nome == "consultar_catalogo" and dado.get("modo") == "sql"), None)
    if consulta is None or consulta.get("estado") not in ("ok", "sem_linhas"):
        return {"estado": "sem_consulta_valida"}
    from .contracts import Evidencia
    sql = consulta["tentativas"][-1]["sql"]
    linhas = consulta.get("linhas", [])
    if not linhas:
        corpo = "A consulta não devolveu nenhuma linha; pode ser que esteja mal formulada."
    else:
        colunas = list(linhas[0])
        corpo = "\n".join(
            ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
            + ["| " + " | ".join(str(linha[c]) for c in colunas) + " |"
               for linha in linhas[:LINHAS_VISIVEIS]])
        if len(linhas) > LINHAS_VISIVEIS or consulta.get("truncado"):
            corpo += f"\n\nSão mostradas {min(len(linhas), LINHAS_VISIVEIS)} de {len(linhas)} linhas" + (
                " (o resultado foi cortado no limite)." if consulta.get("truncado") else ".")
    resposta.mensagem = (f"{consulta.get('explicacao', 'Consulta ao catálogo.')}\n\n{corpo}\n\n"
                         f"Consulta executada (somente leitura): `{sql}`\n"
                         "Os valores estão em centavos de real. A consulta foi escrita por um modelo "
                         "e só se verificou que é segura, não que responde exatamente à pergunta.")
    resposta.dataset_id = consulta["dataset_id"]
    resposta.evidencias = [Evidencia(tipo="catalogo", fonte_id="SQL", texto=sql,
                                     dataset_id=consulta["dataset_id"])]
    return {"estado": "ancorada", "linhas": len(linhas), "sql": sql}


def ancorar_preferencia(resposta: RespostaCompra,
                        observacoes: list[tuple[str, dict]] | None) -> dict | None:
    """Redige a confirmação de uma preferência com o que a ferramenta salvou de verdade."""
    if resposta.estado != "preferencia":
        return None
    salva = next((dado for nome, dado in (observacoes or [])
                  if nome == "salvar_preferencia" and dado.get("estado") == "ok"), None)
    if salva is None:
        return {"estado": "sem_salvamento"}
    resposta.mensagem = f"Salvei a sua preferência: {salva['chave']} = {salva['valor']}."
    return {"estado": "ancorada", "chave": salva["chave"], "valor": salva["valor"]}


def resposta_local(cenario: Cenario, solicitacao) -> RespostaCompra:
    if solicitacao.faltantes() or not solicitacao.produto_id:
        return RespostaCompra(estado="esclarecimento", dataset_id=cenario.dataset_id,
                              solicitacao=solicitacao)
    alternativas = comparar(solicitacao, ofertas(cenario, solicitacao.produto_id))
    validas = [a for a in alternativas if a.atende]
    from .contracts import Evidencia
    return RespostaCompra(
        estado="recomendacao" if validas else "sem_oferta", dataset_id=cenario.dataset_id,
        solicitacao=solicitacao, produto_id=solicitacao.produto_id,
        fornecedor_id=validas[0].oferta.fornecedor_id if validas else None,
        total_centavos=validas[0].total_centavos if validas else None,
        alternativas=alternativas,
        evidencias=[Evidencia(tipo="catalogo", fonte_id=a.oferta.id,
                              dataset_id=cenario.dataset_id,
                              texto=(f"{a.oferta.fornecedor_nome} estoque {a.oferta.estoque} "
                                     f"entrega {a.oferta.prazo_dias} dias")) for a in alternativas])


def melhor_sem_preferencia(resposta: RespostaCompra) -> Alternativa | None:
    """A oferta válida mais barata, se a preferência do usuário fez vencer outra mais cara."""
    if resposta.solicitacao.origem_preferida is None or resposta.estado != "recomendacao":
        return None
    validas = [a for a in resposta.alternativas if a.atende]
    barata = min(validas, key=lambda a: (a.total_centavos, a.oferta.prazo_dias, a.oferta.fornecedor_id))
    vencedora = validas[0]
    return barata if barata.total_centavos < vencedora.total_centavos else None
