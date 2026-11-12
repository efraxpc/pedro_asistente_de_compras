"""Único fluxo de publicação para UI, testes e avaliação."""
import json
import re
from pathlib import Path

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import ConfigurableFieldSpec, RunnableLambda, RunnableWithMessageHistory
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import StructuredTool

from .business import brl, descrever_motivos, descrever_preco, origem_preferida
from .catalog import Cenario, buscar, ficha, listar
from .contracts import Evidencia, RespostaCompra, Solicitacao
from .dialogue import (EstadoCompra, criar_interprete, interpretar_turno,
                       sobre_a_comparacao_em_andamento)
from .integrations import consultar_cep
from .memory import (FastEmbedder, Historico, dataset_sessao, ler_rascunho, preferencias,
                     recuperar, salvar_episodio, salvar_preferencia, salvar_rascunho,
                     tem_episodios)
from .nli import Classificador, verificar_nli
from .policy_demo import (FRAGMENTO_T24_ESPERADO, ORIGEM as ORIGEM_DEMO,
                          PERGUNTA_T24_ORIGINAL, PERGUNTA_T24_REESCRITA,
                          reescrever_consulta_entrega)
from .planner import planejar_turno
from .precos import aconselhar, aviso_de_preco, criar_conselheiro
from .resposta_direta import criar_respondedor, e_pergunta, responder
from .prompts import EXEMPLOS_ACOES, MODELO_AGENTE
from .query import criar_gerador_sql, executar, planejar, responder_sql
from .rag import consultar, diagnosticar_reescrita
from .verification import (ancorar_catalogo, ancorar_cep, ancorar_citacoes, ancorar_preferencia,
                           ancorar_recomendacao, melhor_sem_preferencia, resposta_local,
                           verificar)


# Respostas cujo conteúdo não sai do catálogo: o cenário delas é definido pelo sistema.
ESTADOS_SEM_DADOS_DE_CATALOGO = ("politica", "esclarecimento", "sem_evidencia", "preferencia")


class Rastro(BaseCallbackHandler):
    def __init__(self):
        self.eventos: list[dict] = []

    @staticmethod
    def _seguro(valor: str) -> str:
        return re.sub(r"\b(?:sk|lsv2|lsat)_[A-Za-z0-9_-]{12,}\b|\bsk-[A-Za-z0-9_-]{12,}\b",
                      "[CHAVE OMITIDA]", valor)[:2000]

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        nome = serialized.get("name")
        self.eventos.append({"evento": "tool_start", "rota": nome, "ferramenta": nome,
                             "entrada": self._seguro(input_str)[:1000]})

    def on_tool_end(self, output, **kwargs) -> None:
        resultado = self._seguro(str(output))
        try:
            dado = json.loads(str(output))
            fontes = [e.get("fonte_id") for e in dado.get("evidencias", [])]
        except (ValueError, AttributeError, TypeError):
            fontes = []
        self.eventos.append({"evento": "tool_end", "resultado": resultado,
                             "fontes": [f for f in fontes if f]})

    def registrar_citacoes(self, citacoes: list[dict]) -> None:
        if citacoes:
            self.eventos.append({"evento": "citacoes_ancoradas", "citacoes": citacoes})

    def registrar_verificacao(self, tentativa: int, estado: str | None, erros: list[str]) -> None:
        self.eventos.append({"evento": "verificacao", "tentativa": tentativa, "estado": estado,
                             "erros": list(erros)})

    def on_tool_error(self, error, **kwargs) -> None:
        self.eventos.append({"evento": "tool_error", "tipo": type(error).__name__})

    def on_chain_error(self, error, **kwargs) -> None:
        self.eventos.append({"evento": "chain_error", "tipo": type(error).__name__})


def ferramentas(cenario: Cenario, memoria_db: Path, user_id: str,
                mensagem_atual: str, indice=None, *, cep_simulado: bool = False, llm=None):
    def buscar_produtos(texto: str) -> str:
        """Busca candidatos por ID, SKU ou nome no cenário ativo."""
        return json.dumps({"dataset_id": cenario.dataset_id, "candidatos": buscar(cenario, texto)}, ensure_ascii=False)

    def consultar_catalogo(pergunta: str) -> str:
        """Consulta o catálogo. Com um ID devolve a ficha ou as ofertas; sem ID responde perguntas
        abertas (quantas, quais, rankings) com uma consulta SQL somente leitura validada."""
        try:
            return json.dumps({"modo": "plano", **executar(cenario, pergunta, planejar(pergunta))},
                              ensure_ascii=False)
        except ValueError:
            if llm is None:
                raise
        # Pergunta aberta: o modelo escreve o SELECT e o motor decide se o executa.
        resultado = responder_sql(cenario, pergunta, criar_gerador_sql(llm))
        return json.dumps({"modo": "sql", **resultado}, ensure_ascii=False)

    def comparar_ofertas(produto_id: str, quantidade: int,
                         orcamento_centavos: int | None = None,
                         prazo_max_dias: int | None = None) -> str:
        """Calcula todas as ofertas e os seus descartes exatos em centavos."""
        from .verification import resposta_local
        # A preferência salva do usuário é aplicada pela ferramenta, não pelo modelo.
        solicitacao = Solicitacao(produto_id=produto_id, quantidade=quantidade,
                                  orcamento_centavos=orcamento_centavos,
                                  prazo_max_dias=prazo_max_dias,
                                  origem_preferida=origem_preferida(preferencias(memoria_db, user_id)))
        return resposta_local(cenario, solicitacao).model_dump_json()

    def consultar_politicas(pergunta: str) -> str:
        """Recupera políticas, incluída a entrega em várias caixas, com fontes."""
        reescrita = reescrever_consulta_entrega(pergunta)
        diagnostico = None
        if indice is not None and reescrita is not None:
            referencia = indice.docstore.search(FRAGMENTO_T24_ESPERADO)
            if getattr(referencia, "metadata", {}).get("origem") == ORIGEM_DEMO:
                relatorio = diagnosticar_reescrita(
                    indice, pergunta, reescrita, FRAGMENTO_T24_ESPERADO, k=4)
                fragmentos = relatorio["depois"]
                diagnostico = {
                    "metrica": relatorio["metrica"], "k": relatorio["k"],
                    "fonte_esperada": FRAGMENTO_T24_ESPERADO,
                    "posicao_antes": relatorio["posicao_antes"],
                    "posicao_depois": relatorio["posicao_depois"],
                    "correcao_observada": relatorio["correcao_observada"],
                    "antes": [{"fonte_id": r["fonte_id"], "score": r["score"]}
                              for r in relatorio["antes"]],
                    "depois": [{"fonte_id": r["fonte_id"], "score": r["score"]}
                               for r in relatorio["depois"]],
                }
            else:
                import faiss

                antes = consultar(indice, pergunta)
                fragmentos = consultar(indice, reescrita)
                diagnostico = {
                    "metrica": "L2" if indice.index.metric_type == faiss.METRIC_L2 else "IP",
                    "k": 4,
                    "antes": [{"fonte_id": r["fonte_id"], "score": r["score"]}
                              for r in antes],
                    "depois": [{"fonte_id": r["fonte_id"], "score": r["score"]}
                               for r in fragmentos],
                }
        else:
            fragmentos = consultar(indice, pergunta)
        return json.dumps({
            "fragmentos": fragmentos,
            "estado": "ok" if fragmentos else
                      "sem_evidencia" if indice is not None else "indisponivel",
            "consulta_original": pergunta,
            "consulta_reescrita": reescrita,
            "diagnostico": diagnostico,
        }, ensure_ascii=False)

    def consultar_cep_ferramenta(cep: str) -> str:
        """Confirma cidade e UF com o ViaCEP; não calcula frete."""
        return json.dumps(consultar_cep(cep, simulado=cep_simulado), ensure_ascii=False)

    def salvar_preferencia_ferramenta(chave: str, valor: str, citacao_usuario: str) -> str:
        """Salva somente preferências citadas explicitamente pelo usuário atual."""
        valida = (citacao_usuario in mensagem_atual and valor.lower() in citacao_usuario.lower() and
                  bool(re.search(r"\b(prefiro|guarda|guarde|salva|salve|lembra|lembre|prefer[eê]ncia)\b",
                                 citacao_usuario, re.I)))
        if not valida:
            return json.dumps({"estado": "invalido", "erro": "sem pedido explícito"})
        salvar_preferencia(memoria_db, user_id, chave, valor, explicita=True)
        return json.dumps({"estado": "ok", "chave": chave, "valor": valor})

    return [StructuredTool.from_function(buscar_produtos, name="buscar_produtos"),
            StructuredTool.from_function(consultar_catalogo, name="consultar_catalogo"),
            StructuredTool.from_function(comparar_ofertas, name="comparar_ofertas"),
            StructuredTool.from_function(consultar_politicas, name="consultar_politicas"),
            StructuredTool.from_function(consultar_cep_ferramenta, name="consultar_cep"),
            StructuredTool.from_function(salvar_preferencia_ferramenta, name="salvar_preferencia")]


def criar_agente(cenario: Cenario, memoria_db: Path, user_id: str,
                 mensagem_atual: str, llm, indice=None, *, cep_simulado: bool = False) -> AgentExecutor:
    parser = PydanticOutputParser(pydantic_object=RespostaCompra)
    prompt = MODELO_AGENTE.partial(dataset_id=cenario.dataset_id, exemplos=EXEMPLOS_ACOES,
                                   formato=parser.get_format_instructions())
    lista = ferramentas(cenario, memoria_db, user_id, mensagem_atual, indice,
                        cep_simulado=cep_simulado, llm=llm)
    return AgentExecutor(agent=create_openai_tools_agent(llm, lista, prompt), tools=lista,
                         return_intermediate_steps=True, max_iterations=6)


def _plural_origem(origem: str) -> str:
    """«nacional» → «nacionais», «internacional» → «internacionais»."""
    return origem[:-1] + "is"


def renderizar(resposta: RespostaCompra, *, indice=None, conselho: str | None = None) -> str:
    if resposta.estado == "esclarecimento":
        if not (resposta.solicitacao.produto_id or resposta.solicitacao.produto):
            return "De qual peça você precisa? Indique o ID ou SKU."
        if resposta.solicitacao.quantidade is None:
            return "De quantas unidades você precisa?"
        return "Qual é o ID exato da peça?"
    if resposta.estado == "sem_evidencia":
        return "Não posso confirmar a resposta com as fontes disponíveis."
    if resposta.estado == "catalogo":
        return resposta.mensagem
    if resposta.estado == "preferencia":
        return resposta.mensagem + " Vou levá-la em conta, mas o seu pedido de cada momento é o que manda."
    if resposta.estado == "cep":
        return (f"CEP {resposta.solicitacao.cep}: {resposta.cidade}/{resposta.uf} "
                f"(ViaCEP, modo {resposta.modo_cep}).")
    if resposta.estado == "politica":
        ficticia = indice is not None and any(
            getattr(indice.docstore.search(e.fonte_id), "metadata", {}).get("origem") == ORIGEM_DEMO
            for e in resposta.evidencias if e.tipo == "politica")
        prefixo = "Política fictícia de demonstração. " if ficticia else ""
        return prefixo + resposta.mensagem + "\nFontes: " + ", ".join(
            e.fonte_id for e in resposta.evidencias if e.tipo == "politica")
    if resposta.estado == "sem_oferta":
        inicio = "Nenhuma oferta atende às restrições indicadas."
    else:
        vencedora = next(a for a in resposta.alternativas if a.oferta.fornecedor_id == resposta.fornecedor_id)
        inicio = (f"{vencedora.oferta.fornecedor_nome}: {brl(vencedora.total_centavos)} "
                  f"para {resposta.solicitacao.quantidade} unidades; prazo de {vencedora.oferta.prazo_dias} dias.")
    linhas = [inicio]
    for a in resposta.alternativas:
        linhas.append(f"- {a.oferta.fornecedor_nome} ({'nacional' if a.oferta.nacional else 'internacional'}): "
                      f"{brl(a.total_centavos)}; "
                      f"{'atende' if a.atende else 'descartada por ' + descrever_motivos(a)} "
                      f"[{a.oferta.id}]")
    historico = [texto for a in resposta.alternativas if a.atende
                 if (texto := descrever_preco(a.oferta))]
    if historico:
        linhas.append("Histórico de preços (informativo; não muda a recomendação):")
        linhas.extend(f"- {texto}" for texto in historico)
    # Aviso de preço: o conselho verificado do modelo, se houver; se não, o aviso de modelo fixo.
    if conselho:
        linhas.append(f"Conselho sobre o preço (redigido pelo modelo e verificado): {conselho}")
    elif aviso := aviso_de_preco(resposta):
        linhas.append(f"Aviso de preço: {aviso}")
    if resposta.solicitacao.origem_preferida:
        nota = ("Foi aplicada a sua preferência por fornecedores "
                f"{_plural_origem(resposta.solicitacao.origem_preferida)}.")
        barata = melhor_sem_preferencia(resposta)
        if barata is not None:
            nota += (f" Sem ela, a mais barata seria {barata.oferta.fornecedor_nome} "
                     f"por {brl(barata.total_centavos)}.")
        linhas.append(nota)
    linhas.append("Fontes: " + ", ".join(e.fonte_id for e in resposta.evidencias))
    return "\n".join(linhas)


def renderizar_citacoes(resposta: RespostaCompra, *, indice=None) -> str:
    """Resposta extrativa: somente texto literal das fontes, sem resumo do modelo."""
    citacoes = [e for e in resposta.evidencias if e.tipo == "politica"]
    ficticia = indice is not None and any(
        getattr(indice.docstore.search(e.fonte_id), "metadata", {}).get("origem") == ORIGEM_DEMO
        for e in citacoes)
    prefixo = "Política fictícia de demonstração. " if ficticia else ""
    return (prefixo + "Não consegui verificar um resumo próprio, então cito o texto literal "
            "da fonte:\n" + "\n".join(f"- «{e.texto}» [{e.fonte_id}]" for e in citacoes))


def e_diagnostico_t24(pergunta: str) -> bool:
    """Reconhece o comando de demonstração controlada do chat."""
    return pergunta.strip().casefold() in {"/t24", "t24", "teste t24"}


def resumo_recuperacao_t24(diagnostico: dict | None) -> str:
    """Descreve um contraste observado pela ferramenta, sem inferência do LLM."""
    if not diagnostico or not diagnostico.get("correcao_observada"):
        return ""
    return (
        f"Recuperação T24: a pergunta inicial deixou "
        f"`{diagnostico['fonte_esperada']}` fora do top-{diagnostico['k']}; "
        f"a reformulação o colocou na posição "
        f"{diagnostico['posicao_depois']} com o mesmo índice e top-k."
    )


# Frases da regra de entrega parcial no corpus fictício (knowledge/politicas_demo/entrega.md).
_FRASES_ENTREGA_PARCIAL = (r"Uma entrega parcial[^.]*\.",
                           r"Se n[aã]o (?:existe|existir|houver) esse acordo[^.]*\.")


def resolver_entrega_parcial(cenario: Cenario, memoria_db: Path, usuario: str,
                             pergunta: str, indice, classificador: Classificador | None,
                             rastro: Rastro | None = None) -> str | None:
    """Rota extrativa verificada para perguntas de envio dividido do corpus demo."""
    if indice is None or reescrever_consulta_entrega(pergunta) is None:
        return None
    referencia = indice.docstore.search(FRAGMENTO_T24_ESPERADO)
    if getattr(referencia, "metadata", {}).get("origem") != ORIGEM_DEMO:
        return None
    ferramenta = next(f for f in ferramentas(cenario, memoria_db, usuario,
                                             pergunta, indice)
                      if f.name == "consultar_politicas")
    try:
        resultado_tool = ferramenta.invoke(
            {"pergunta": pergunta}, config={"callbacks": [rastro] if rastro else []})
        dado_tool = json.loads(resultado_tool)
    except Exception:
        return "Não consegui consultar as políticas fictícias para esta pergunta."
    diagnostico = dado_tool.get("diagnostico")
    if not diagnostico or not diagnostico.get("correcao_observada"):
        return "Não consegui confirmar uma recuperação corrigida para esta pergunta."
    fragmento = next((f for f in dado_tool.get("fragmentos", [])
                      if f.get("fonte_id") == FRAGMENTO_T24_ESPERADO), None)
    if fragmento is None:
        return "A reformulação não recuperou a regra de entrega parcial."
    fonte = fragmento["texto"]
    frases = [coincidencia.group(0) for padrao in _FRASES_ENTREGA_PARCIAL
              if (coincidencia := re.search(padrao, fonte))]
    if len(frases) != 2:
        return "O fragmento recuperado não contém a regra completa de entrega parcial."
    resposta = RespostaCompra(
        estado="politica", dataset_id=cenario.dataset_id, solicitacao=Solicitacao(),
        mensagem=" ".join(frases),
        evidencias=[Evidencia(tipo="politica", fonte_id=FRAGMENTO_T24_ESPERADO,
                              texto=fonte)],
    )
    if verificar(resposta, cenario, indice=indice,
                 observacoes=[("consultar_politicas", dado_tool)]):
        return "Encontrei a regra, mas não consegui verificar a sua fonte no índice."
    if classificador is None or not verificar_nli(resposta, classificador):
        return ("Encontrei o fragmento de entrega parcial, mas não consegui verificar "
                "a resposta com o NLI local; não confirmo a regra.")
    return renderizar(resposta, indice=indice) + "\n\n" + resumo_recuperacao_t24(diagnostico)


def renderizar_diagnostico_t24(indice) -> str:
    """Mostra a mesma comparação reproduzível do notebook, sem LLM."""
    if indice is None:
        return "Não foi possível carregar o índice fictício necessário para o teste T24."
    try:
        relatorio = diagnosticar_reescrita(
            indice, PERGUNTA_T24_ORIGINAL, PERGUNTA_T24_REESCRITA,
            FRAGMENTO_T24_ESPERADO, k=4)
    except ValueError:
        return "O teste T24 requer o corpus fictício de políticas de demonstração."

    introducao = [
        "### Teste T24 · recuperação fictícia",
        f"Pergunta inicial: {PERGUNTA_T24_ORIGINAL}",
        f"Reformulação: {PERGUNTA_T24_REESCRITA}",
        f"Índice: {relatorio['total_fragmentos']} fragmentos; métrica {relatorio['metrica']}; "
        f"top-{relatorio['k']} nas duas buscas.",
    ]
    tabela = [
        "| Consulta | Posição | Fragmento | Fonte / seção | Distância L2 |",
        "|---|---:|---|---|---:|",
    ]
    for etapa, rotulo in (("antes", "Inicial"), ("depois", "Reformulada")):
        for resultado in relatorio[etapa]:
            meta = resultado["metadados"]
            tabela.append(
                f"| {rotulo} | {resultado['posicao']} | `{resultado['fonte_id']}` | "
                f"{meta.get('fonte', '?')} / {meta.get('secao', '?')} | "
                f"{resultado['score']:.3f} |"
            )
    posicao_antes = relatorio["posicao_antes"] or "fora do top-4"
    posicao_depois = relatorio["posicao_depois"] or "fora do top-4"
    detalhes = [
        f"Fragmento esperado `{FRAGMENTO_T24_ESPERADO}`: antes {posicao_antes}; "
        f"depois {posicao_depois}. "
        "Fonte: entrega.md, seção «Entrega parcial e estoque». "
        "Em L2, uma distância menor indica maior proximidade."
    ]
    regra = re.search(_FRASES_ENTREGA_PARCIAL[0],
                      relatorio["evidencia_esperada"]["texto"])
    if regra:
        detalhes.append(f"Regra no fragmento fonte: «{regra.group(0)}»")
    filtrados = consultar(indice, PERGUNTA_T24_ORIGINAL, k=4,
                          filtro={"tema": "entrega"}, fetch_k=indice.index.ntotal)
    posicao_filtro = next((r["posicao"] for r in filtrados
                           if r["fonte_id"] == FRAGMENTO_T24_ESPERADO), None)
    detalhes.append(
        f"Teste separado com filtro `tema=entrega`: fragmento esperado na posição "
        f"{posicao_filtro if posicao_filtro is not None else 'fora do top-4'}."
    )
    if not relatorio["correcao_observada"]:
        detalhes.append("A correção não se reproduz mais com este índice; revise o corpus e o modelo.")
    detalhes.append("Demonstração sintética: falta repeti-la no índice preexistente para R22/R23.")
    return "\n\n".join(introducao + ["\n".join(tabela)] + detalhes)


def consulta_direta(cenario: Cenario, pergunta: str) -> str | None:
    texto = pergunta.lower()
    ids = re.findall(r"\bPEC-[0-9]{2}-[0-9]{4}\b", pergunta.upper())
    if re.search(r"\b(ficha|detalhes?|compatibilidade)\b", texto) and len(set(ids)) == 1:
        dado = ficha(cenario, ids[0])
        if dado is None:
            return "Peça não encontrada."
        return (f"{dado['name']} ({dado['id']}, SKU {dado['sku']}). {dado['description']} "
                f"Compatibilidade fictícia: " + ", ".join(
                    f"{c['brand']} {c['model_code']}" for c in dado["compatibility"]))
    if (re.search(r"\b(lista|listar|liste|mostra|mostre|cat[aá]logo)\b", texto)
            and re.search(r"\b(pe[cç]as|reposi[cç][aã]o|cat[aá]logo)\b", texto)
            and not re.search(r"\b(oferta|pre[cç]o|estoque|comparar)\b", texto)):
        pagina = re.search(r"p[aá]gina\s+(\d+)", texto)
        numero = int(pagina.group(1)) if pagina else 1
        total, pecas = listar(cenario, numero)
        return f"Peças do cenário ({total}; página {numero}):\n" + "\n".join(
            f"- {p['id']} · {p['sku']} · {p['name']}" for p in pecas)
    return None


CHAVE_PARTES = "partes"


def _com_direta(texto: str, direta: dict | None) -> str:
    """Põe a resposta à pergunta do usuário antes da comparação completa."""
    return texto if direta is None else f"{direta['texto']}\n\n{texto}"


def mensagem_publica(texto: str, resposta: RespostaCompra | None = None,
                     conselho: str | None = None, titulo: str | None = None,
                     direta: dict | None = None) -> AIMessage:
    """Resposta pública de um pedido.

    O texto é a resposta completa e é a única coisa que o modelo lê em turnos posteriores.
    Para uma comparação de ofertas anexa-se também, como metadados, a resposta
    estruturada já verificada: a interface a usa para desenhar cartões e tabela em vez de
    texto. São os mesmos dados do texto, não informação adicional.
    """
    parte: dict = {"titulo": titulo, "texto": texto, "comparacao": None, "conselho": conselho,
                   "direta": direta}
    if resposta is not None and resposta.estado in ("recomendacao", "sem_oferta"):
        parte["comparacao"] = resposta.model_dump(mode="json")
    return AIMessage(content=texto, additional_kwargs={CHAVE_PARTES: [parte]})


def partes_de(mensagem) -> list[dict]:
    """Partes estruturadas de uma mensagem do assistente; uma única de texto se não trouxer."""
    partes = getattr(mensagem, "additional_kwargs", {}).get(CHAVE_PARTES)
    return partes or [{"titulo": None, "texto": str(mensagem.content), "comparacao": None,
                       "conselho": None}]


def criar_fluxo(cenario: Cenario, memoria_db: Path, *, llm=None,
                classificador: Classificador | None = None, indice=None,
                cep_simulado: bool = False, rastro: Rastro | None = None):
    parser = PydanticOutputParser(pydantic_object=RespostaCompra)

    def turno(dado: dict, config: RunnableConfig) -> AIMessage:
        """Um turno do chat: se a mensagem traz várias intenções, planeja-se e responde-se
        cada pedido separadamente, com a sua própria verificação."""
        mensagem = dado["input"]
        pedidos = planejar_turno(mensagem, llm)
        if pedidos is None:
            return resolver(dado, config, mensagem)
        if rastro:
            rastro.eventos.append({"evento": "plano", "pedidos": [p.model_dump() for p in pedidos]})
        entrada = f"Sua mensagem tinha {len(pedidos)} pedidos; respondo cada um separadamente."
        textos = [entrada]
        partes: list[dict] = [{"titulo": None, "texto": entrada, "comparacao": None, "conselho": None}]
        for numero, pedido in enumerate(pedidos, 1):
            resposta = resolver({**dado, "input": pedido.pedido}, config, mensagem)
            titulo = f"{numero}. {pedido.pedido}"
            textos.append(f"**{titulo}**\n{resposta.content}")
            partes.extend({**parte, "titulo": titulo} for parte in partes_de(resposta))
        return AIMessage(content="\n\n".join(textos), additional_kwargs={CHAVE_PARTES: partes})

    def resolver(dado: dict, config: RunnableConfig, mensagem_usuario: str) -> AIMessage:
        """Resolve um pedido de uma única intenção."""
        usuario = config["configurable"]["user_id"]
        sessao = config["configurable"]["session_id"]
        if dataset_sessao(memoria_db, usuario, sessao) != cenario.dataset_id:
            raise ValueError("dataset da sessão diferente do cenário")
        pergunta = dado["input"]
        if e_diagnostico_t24(pergunta):
            return AIMessage(content=renderizar_diagnostico_t24(indice))
        if reescrever_consulta_entrega(pergunta) is not None:
            politica = resolver_entrega_parcial(cenario, memoria_db, usuario,
                                                pergunta, indice, classificador, rastro)
            if politica is not None:
                return AIMessage(content=politica)
        direta = consulta_direta(cenario, pergunta)
        if direta is not None:
            return AIMessage(content=direta)
        rascunho = ler_rascunho(memoria_db, usuario, sessao)
        previo = EstadoCompra.model_validate(rascunho) if rascunho is not None else None
        interprete = None
        if llm is not None:
            try:
                interprete = criar_interprete(llm)
            except Exception:
                interprete = None
        compra, leitura = interpretar_turno(cenario, previo, pergunta, interprete)
        if rastro and leitura.get("fonte") == "modelo":
            rastro.eventos.append({"evento": "interpretacao", **leitura})
        solicitacao_atual = None
        if compra is not None:
            estado, esclarecimento = compra
            salvar_rascunho(memoria_db, usuario, sessao, estado.model_dump())
            if esclarecimento is not None:
                return AIMessage(content=esclarecimento)
            solicitacao_atual = estado.solicitacao
            # A preferência salva entra na solicitação: assim também pode ser verificada.
            solicitacao_atual.origem_preferida = origem_preferida(preferencias(memoria_db, usuario))
            if llm is None:
                proposta = resposta_local(cenario, solicitacao_atual)
                erros = verificar(proposta, cenario)
                if erros:
                    return AIMessage(content="Não posso confirmar uma recomendação com as evidências disponíveis.")
                direta = responder(proposta, pergunta, None, None) if e_pergunta(pergunta) else None
                return mensagem_publica(_com_direta(renderizar(proposta), direta), proposta,
                                        direta=direta)
            sem_mudancas = previo is not None and (
                solicitacao_atual.model_dump(exclude={"origem_preferida"})
                == previo.solicitacao.model_dump(exclude={"origem_preferida"}))
            if sem_mudancas and sobre_a_comparacao_em_andamento(cenario, previo, pergunta):
                # Pergunta sobre as ofertas já comparadas: o sistema refaz o cálculo (não depende
                # de o modelo voltar a chamar a ferramenta) e o modelo só redige a frase.
                proposta = resposta_local(cenario, solicitacao_atual)
                erros = verificar(proposta, cenario)
                if not erros and proposta.estado == "recomendacao" and (
                        classificador is None or not verificar_nli(proposta, classificador)):
                    erros = ["NLI sem entailment"]
                if rastro:
                    rastro.eventos.append({"evento": "comparacao_reutilizada",
                                           "fontes": [a.oferta.id for a in proposta.alternativas]})
                    rastro.registrar_verificacao(1, proposta.estado, erros)
                if not erros:
                    try:
                        respondedor = criar_respondedor(llm)
                    except Exception:
                        respondedor = None
                    direta = responder(proposta, pergunta, respondedor, classificador)
                    if rastro:
                        rastro.eventos.append({"evento": "resposta_direta", **{
                            chave: direta.get(chave) for chave in
                            ("fonte", "texto", "rejeitada", "erros")}})
                    texto = _com_direta(renderizar(proposta), direta)
                    try:
                        salvar_episodio(memoria_db, usuario, sessao, pergunta + " | " + texto,
                                        FastEmbedder())
                    except Exception:
                        pass
                    return mensagem_publica(texto, proposta, direta=direta)
        if llm is None:
            return AIMessage(content="Posso comparar peças aqui. Indique um ID ou SKU e a quantidade; para políticas ou CEP configure OPENAI_API_KEY.")
        lembrancas = []
        if tem_episodios(memoria_db, usuario):
            try:
                lembrancas = recuperar(memoria_db, usuario, pergunta, FastEmbedder())
            except Exception:
                pass
        contexto = "\n".join(f"Lembrança histórica ({r['dataset_id']}): {r['texto']}" for r in lembrancas)
        pref = preferencias(memoria_db, usuario)
        erros = []
        extrativa = None
        cep_falho = None
        for tentativa in range(2):
            entrada = pergunta
            if solicitacao_atual is not None:
                entrada += ("\nSolicitação estruturada vigente (o pedido atual já prevaleceu sobre o "
                            "histórico; respeite-a exatamente): " + solicitacao_atual.model_dump_json())
            if contexto:
                entrada += "\n" + contexto + "\nNão use preços ou estoque históricos."
            if pref:
                entrada += "\nPreferências subordinadas ao pedido atual: " + json.dumps(pref)
            if erros:
                entrada += "\nCorrija estes erros observáveis: " + "; ".join(erros)
            # As preferências são validadas contra o que o usuário escreveu, não contra o plano.
            executor = criar_agente(cenario, memoria_db, usuario, mensagem_usuario, llm, indice,
                                    cep_simulado=cep_simulado)
            try:
                saida = executor.invoke({"input": entrada, "chat_history": dado["chat_history"]},
                    config={"callbacks": [rastro] if rastro else [],
                            "metadata": {"dataset_id": cenario.dataset_id, "user_id": usuario,
                                         "session_id": sessao, "proposta": tentativa + 1}})
                proposta = parser.parse(saida["output"])
                observacoes = []
                for acao, resultado_tool in saida.get("intermediate_steps", []):
                    try:
                        observacoes.append((acao.tool, json.loads(str(resultado_tool))))
                    except (ValueError, TypeError, AttributeError):
                        pass
                cep_falho = next((dado_tool for nome, dado_tool in observacoes
                                  if nome == "consultar_cep" and dado_tool.get("estado") != "ok"),
                                 cep_falho)
                citacoes = ancorar_citacoes(proposta, observacoes)
                cep = ancorar_cep(proposta, observacoes, cenario.dataset_id)
                if rastro:
                    rastro.registrar_citacoes(citacoes)
                    if cep:
                        rastro.eventos.append({"evento": "cep_ancorado", **cep})
                if proposta.estado in ESTADOS_SEM_DADOS_DE_CATALOGO:
                    # O identificador do cenário é conhecido pelo sistema; não se pede ao
                    # modelo que copie 36 caracteres em respostas que não usam o catálogo.
                    proposta.dataset_id = cenario.dataset_id
                comparacao = ancorar_recomendacao(proposta, observacoes)
                if rastro and comparacao:
                    rastro.eventos.append({"evento": "comparacao_ancorada", **comparacao})
                catalogo = ancorar_catalogo(proposta, observacoes)
                if rastro and catalogo:
                    rastro.eventos.append({"evento": "catalogo_ancorado", **catalogo})
                preferencia = ancorar_preferencia(proposta, observacoes)
                if rastro and preferencia:
                    rastro.eventos.append({"evento": "preferencia_ancorada", **preferencia})
                erros = verificar(proposta, cenario, indice=indice,
                                  observacoes=observacoes)
                if solicitacao_atual is not None and proposta.estado not in (
                        "recomendacao", "sem_oferta", "sem_evidencia"):
                    erros.append("resposta alheia à comparação solicitada")
                if solicitacao_atual is not None and proposta.estado in ("recomendacao", "sem_oferta"):
                    campos = ("produto_id", "quantidade", "orcamento_centavos", "prazo_max_dias")
                    if any(getattr(proposta.solicitacao, c) != getattr(solicitacao_atual, c) for c in campos):
                        erros.append("solicitação diferente do pedido vigente")
                if not erros and proposta.estado in ("recomendacao", "politica"):
                    if classificador is None or not verificar_nli(proposta, classificador):
                        erros = ["NLI sem entailment"]
                        if proposta.estado == "politica" and solicitacao_atual is None:
                            # As citações já são literais e verificadas; só falhou o resumo.
                            extrativa = proposta
                if rastro:
                    rastro.registrar_verificacao(tentativa + 1, proposta.estado, erros)
                if not erros:
                    conselho = None
                    if proposta.estado == "recomendacao":
                        try:
                            conselheiro = criar_conselheiro(llm)
                        except Exception:
                            conselheiro = None
                        preco = aconselhar(proposta, conselheiro, classificador)
                        if preco["fonte"] == "conselho verificado":
                            conselho = preco["texto"]
                        if rastro and preco["fonte"] != "nada a avisar":
                            rastro.eventos.append({"evento": "conselho_preco", **{
                                chave: preco.get(chave) for chave in
                                ("fonte", "texto", "conselho_rejeitado", "erros")}})
                    texto = renderizar(proposta, indice=indice, conselho=conselho)
                    direta = None
                    if proposta.estado in ("recomendacao", "sem_oferta") and e_pergunta(pergunta):
                        try:
                            respondedor = criar_respondedor(llm)
                        except Exception:
                            respondedor = None
                        direta = responder(proposta, pergunta, respondedor, classificador)
                        texto = _com_direta(texto, direta)
                        if rastro:
                            rastro.eventos.append({"evento": "resposta_direta", **{
                                chave: direta.get(chave) for chave in
                                ("fonte", "texto", "rejeitada", "erros")}})
                    if proposta.estado == "politica":
                        fontes_publicadas = {e.fonte_id for e in proposta.evidencias
                                             if e.tipo == "politica"}
                        for nome, dado_tool in observacoes:
                            diagnostico = dado_tool.get("diagnostico") if nome == "consultar_politicas" else None
                            if (diagnostico and diagnostico.get("correcao_observada") and
                                    diagnostico.get("fonte_esperada") in fontes_publicadas):
                                texto += "\n\n" + resumo_recuperacao_t24(diagnostico)
                                break
                    if proposta.estado in ("recomendacao", "sem_oferta"):
                        try:
                            salvar_episodio(memoria_db, usuario, sessao, pergunta + " | " + texto,
                                            FastEmbedder())
                        except Exception:
                            pass
                    return mensagem_publica(texto, proposta, conselho, direta=direta)
            except Exception as exc:
                erros = [type(exc).__name__]
                if rastro:
                    rastro.registrar_verificacao(tentativa + 1, None, erros)
        if extrativa is not None:
            return AIMessage(content=renderizar_citacoes(extrativa, indice=indice))
        if cep_falho is not None:
            # A API respondeu, mas sem cidade: diz-se o que aconteceu em vez de inventar um destino.
            motivos = {"nao_encontrado": f"O ViaCEP não tem registro do CEP {cep_falho.get('cep')}.",
                       "invalido": "Um CEP deve ter oito dígitos.",
                       "indisponivel": "O ViaCEP não respondeu; tente novamente mais tarde."}
            return AIMessage(content=motivos.get(cep_falho.get("estado"),
                                                 "Não consegui confirmar esse CEP com o ViaCEP."))
        if indice is not None and re.search(r"\b(pol[ií]tica|entrega|devolu[cç][aã]o|garantia)\b",
                                            pergunta, re.I):
            return AIMessage(content="Não consegui verificar a resposta sobre políticas. "
                                     "Você pode reformular a pergunta ou escrever /t24 para "
                                     "ver o diagnóstico de recuperação.")
        return AIMessage(content="Não posso confirmar uma recomendação com as evidências disponíveis.")

    return RunnableWithMessageHistory(RunnableLambda(turno),
        lambda user_id, session_id: Historico(memoria_db, user_id, session_id),
        input_messages_key="input", history_messages_key="chat_history",
        history_factory_config=[ConfigurableFieldSpec(id="user_id", annotation=str, name="usuário"),
                                ConfigurableFieldSpec(id="session_id", annotation=str, name="sessão")])
