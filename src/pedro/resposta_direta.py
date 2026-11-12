"""Resposta direta a uma pergunta sobre a comparação já calculada.

A comparação é sempre a mesma tabela; a pergunta do usuário muda («a mais barata?», «qual
chega antes?»). Aqui o modelo escreve uma ou duas frases que respondem a essa pergunta usando
só os fatos da comparação, e a frase só é publicada se passar na verificação (números e
fornecedores exatos, depois NLI). Se falhar, publica-se um resumo fixo calculado pelo sistema.
Não muda a recomendação nem os números.
"""
import re

from pydantic import BaseModel, Field

from .business import brl
from .contracts import Alternativa, RespostaCompra
from .nli import Classificador

ESTADOS = ("recomendacao", "sem_oferta")


def e_pergunta(mensagem: str) -> bool:
    """Só se responde de forma direta quando o usuário pergunta algo."""
    return "?" in mensagem


def _origem(alternativa: Alternativa) -> str:
    return "nacional" if alternativa.oferta.nacional else "internacional"


_MOTIVOS = {"estoque": "não tem estoque suficiente",
            "pedido_minimo": "o pedido não chega ao pedido mínimo do fornecedor",
            "prazo": "o prazo de entrega passa do máximo pedido",
            "orcamento": "o total passa do orçamento máximo"}


def _situacao(alternativa: Alternativa) -> str:
    """Frase completa: o NLI entende melhor um motivo escrito por extenso que uma lista."""
    if alternativa.atende:
        return "atende às restrições"
    return "foi descartada porque " + " e porque ".join(_MOTIVOS[m] for m in alternativa.motivos)


def _destaques(resposta: RespostaCompra) -> dict[str, Alternativa | None]:
    """As ofertas que respondem às perguntas mais comuns, calculadas pelo sistema."""
    todas = resposta.alternativas
    validas = [a for a in todas if a.atende]
    recomendada = next((a for a in todas if a.oferta.fornecedor_id == resposta.fornecedor_id), None)
    return {
        "recomendada": recomendada if resposta.estado == "recomendacao" else None,
        "menor_total": min(todas, key=lambda a: a.total_centavos, default=None),
        "menor_total_valida": min(validas, key=lambda a: a.total_centavos, default=None),
        "mais_rapida": min(todas, key=lambda a: a.oferta.prazo_dias, default=None),
        "mais_rapida_valida": min(validas, key=lambda a: a.oferta.prazo_dias, default=None),
    }


def fatos_da_comparacao(resposta: RespostaCompra) -> list[str]:
    """Frases com tudo o que a comparação sabe; são a única fonte da resposta direta."""
    solicitacao = resposta.solicitacao
    limites = []
    if solicitacao.prazo_max_dias is not None:
        limites.append(f"prazo máximo de {solicitacao.prazo_max_dias} dias")
    if solicitacao.orcamento_centavos is not None:
        limites.append(f"orçamento máximo de {brl(solicitacao.orcamento_centavos)}")
    fatos = [f"O pedido é de {solicitacao.quantidade} unidades de {solicitacao.produto_id}, "
             + ("com " + " e ".join(limites) if limites else "sem limite de prazo nem de orçamento") + "."]
    for a in resposta.alternativas:
        fatos.append(
            f"A oferta de {a.oferta.fornecedor_nome} é {_origem(a)}, custa {brl(a.total_centavos)} no total, "
            f"entrega em {a.oferta.prazo_dias} dias, tem estoque de {a.oferta.estoque} unidades e "
            f"pedido mínimo de {a.oferta.pedido_minimo}; {_situacao(a)}.")
    d = _destaques(resposta)
    if d["recomendada"] is not None:
        fatos.append(f"A oferta recomendada é a de {d['recomendada'].oferta.fornecedor_nome}.")
    else:
        fatos.append("Nenhuma oferta atende às restrições.")
    if d["menor_total_valida"] is not None:
        fatos.append("Entre as ofertas que atendem, a mais barata é a de "
                     f"{d['menor_total_valida'].oferta.fornecedor_nome}.")
    if d["menor_total"] is not None:
        fatos.append(f"A oferta de menor total entre todas é a de {d['menor_total'].oferta.fornecedor_nome}.")
    if d["mais_rapida"] is not None:
        fatos.append(f"A entrega mais rápida entre todas é a de {d['mais_rapida'].oferta.fornecedor_nome}.")
    return fatos


def resumo_fixo(resposta: RespostaCompra) -> str:
    """Função hardcoded: o resumo que se publica quando não há resposta verificada do modelo."""
    d = _destaques(resposta)
    barata, valida = d["menor_total"], d["menor_total_valida"]
    if barata is None:
        return "Não há ofertas para comparar."
    if valida is None:
        return (f"Nenhuma oferta atende às restrições. A de menor total é a de "
                f"{barata.oferta.fornecedor_nome}, por {brl(barata.total_centavos)}, mas {_situacao(barata)}.")
    frases = [f"A mais barata que atende às suas restrições é a de {valida.oferta.fornecedor_nome}, "
              f"por {brl(valida.total_centavos)}, com entrega em {valida.oferta.prazo_dias} dias."]
    if barata.oferta.id != valida.oferta.id:
        frases.append(f"A de menor total é a de {barata.oferta.fornecedor_nome}, por "
                      f"{brl(barata.total_centavos)}, mas {_situacao(barata)}.")
    recomendada = d["recomendada"]
    if recomendada is not None and recomendada.oferta.id != valida.oferta.id:
        frases.append(f"A recomendada é a de {recomendada.oferta.fornecedor_nome}, por "
                      f"{brl(recomendada.total_centavos)}, pela sua preferência de origem.")
    return " ".join(frases)


# --- Camada semântica: a frase do modelo, verificada antes de ser publicada. ---

class RespostaDireta(BaseModel):
    """Resposta breve à pergunta do usuário, baseada só nos fatos recebidos."""
    resposta: str = Field(min_length=10, max_length=360,
                          description="Uma ou duas frases que respondem exatamente à pergunta")


def criar_respondedor(modelo):
    """Cadeia LCEL: fatos e pergunta → prompt PTCF com few-shot → modelo → `RespostaDireta`."""
    from langchain_core.output_parsers import PydanticOutputParser

    from .prompts import MODELO_RESPOSTA_DIRETA

    parser = PydanticOutputParser(pydantic_object=RespostaDireta)
    return MODELO_RESPOSTA_DIRETA.partial(formato=parser.get_format_instructions()) | modelo | parser


def _numeros(texto: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)*", texto))


def verificar_resposta_direta(texto: str, fatos: list[str], fornecedores: list[str],
                              classificador: Classificador | None) -> list[str]:
    """Porta da resposta direta: números e fornecedores exatos, e depois NLI."""
    premissa = " ".join(fatos)
    erros = []
    if _numeros(texto) - _numeros(premissa):
        erros.append("a resposta contém números que não estão nos fatos")
    if not any(nome in texto for nome in fornecedores) and "Nenhuma oferta" not in texto:
        erros.append("a resposta não nomeia nenhum fornecedor comparado")
    if erros:
        return erros
    if classificador is None:
        return ["sem classificador NLI"]
    try:
        rotulo = classificador.classificar(premissa, texto)
    except Exception as exc:
        return [f"NLI indisponível ({type(exc).__name__})"]
    return [] if rotulo == "entailment" else [f"NLI: {rotulo}"]


def responder(resposta: RespostaCompra, pergunta: str, respondedor,
              classificador: Classificador | None) -> dict:
    """Devolve o texto a publicar e um relatório para o rastro.

    A frase do modelo é publicada só se passar na verificação; se falhar, ou se não houver
    modelo, publica-se o resumo fixo.
    """
    fixo = resumo_fixo(resposta)
    if respondedor is None:
        return {"texto": fixo, "fonte": "resumo fixo"}
    fatos = fatos_da_comparacao(resposta)
    try:
        texto = respondedor.invoke({"fatos": "\n".join(f"- {f}" for f in fatos),
                                    "pergunta": pergunta}).resposta
    except Exception as exc:
        return {"texto": fixo, "fonte": "resumo fixo", "rejeitada": None,
                "erros": [f"o modelo não devolveu uma resposta válida ({type(exc).__name__})"]}
    fornecedores = [a.oferta.fornecedor_nome for a in resposta.alternativas]
    erros = verificar_resposta_direta(texto, fatos, fornecedores, classificador)
    if erros:
        return {"texto": fixo, "fonte": "resumo fixo", "rejeitada": texto, "erros": erros}
    return {"texto": texto, "fonte": "resposta verificada"}
