"""Aviso de preço: situa o preço de hoje no seu histórico e aconselha com respaldo.

Duas camadas, como no restante do assistente:
- Hardcoded: o sinal de cada oferta e o aviso são calculados com limiares fixos.
- Semântica: um modelo redige um conselho a partir desses fatos, e ele só é publicado se os
  seus números saem dos fatos e um modelo NLI confirma que os fatos o sustentam.
O aviso informa o comprador; não muda qual oferta vence.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

from .business import brl, variacao_percentual
from .contracts import Alternativa, Oferta, RespostaCompra
from .nli import Classificador

LIMIAR_NOTAVEL = 10    # pontos percentuais em relação à média: acima ou abaixo
LIMIAR_FORTE = 20    # muito acima ou muito abaixo
MARGEM_ALTERNATIVA = 5  # uma alternativa «custa quase o mesmo» se o seu total supera o do vencedor em ≤ 5 %
Nivel = Literal["muito acima", "acima", "em linha", "abaixo", "muito abaixo"]


class SinalPreco(BaseModel):
    """Onde está o preço unitário de hoje em relação ao seu histórico."""
    fornecedor: str
    nivel: Nivel
    frente_a_media: int   # pontos percentuais
    frente_a_mes_anterior: int
    no_minimo: bool
    no_maximo: bool


def sinal_preco(oferta: Oferta) -> SinalPreco | None:
    """Função hardcoded: classifica o preço de hoje com limiares fixos."""
    if not oferta.preco_medio_centavos or not oferta.preco_anterior_centavos:
        return None
    atual = oferta.preco_unitario_centavos
    pontos = variacao_percentual(atual, oferta.preco_medio_centavos)
    if pontos >= LIMIAR_FORTE:
        nivel: Nivel = "muito acima"
    elif pontos >= LIMIAR_NOTAVEL:
        nivel = "acima"
    elif pontos <= -LIMIAR_FORTE:
        nivel = "muito abaixo"
    elif pontos <= -LIMIAR_NOTAVEL:
        nivel = "abaixo"
    else:
        nivel = "em linha"
    return SinalPreco(fornecedor=oferta.fornecedor_nome, nivel=nivel, frente_a_media=pontos,
                      frente_a_mes_anterior=variacao_percentual(atual, oferta.preco_anterior_centavos),
                      no_minimo=atual == oferta.preco_minimo_centavos,
                      no_maximo=atual == oferta.preco_maximo_centavos)


def _validas(resposta: RespostaCompra) -> list[Alternativa]:
    return [a for a in resposta.alternativas if a.atende]


def _frase_sinal(sinal: SinalPreco, meses: int) -> str:
    if sinal.nivel == "em linha":
        frase = f"O preço de {sinal.fornecedor} está em linha com a sua média de {meses} meses"
    else:
        frase = (f"O preço de {sinal.fornecedor} está {abs(sinal.frente_a_media)} % "
                 f"{'acima' if sinal.frente_a_media > 0 else 'abaixo'} da sua média de {meses} meses")
    if sinal.no_minimo:
        frase += " e é o mais baixo do período"
    elif sinal.no_maximo:
        frase += " e é o mais alto do período"
    return frase + "."


def fatos_de_preco(resposta: RespostaCompra) -> list[str]:
    """Fatos verificáveis sobre os preços, em frases. São a premissa do conselho."""
    if resposta.estado != "recomendacao":
        return []
    validas = _validas(resposta)
    vencedora = validas[0]
    fatos = [f"A oferta recomendada é a de {vencedora.oferta.fornecedor_nome}, com um total de "
             f"{brl(vencedora.total_centavos)} e entrega em {vencedora.oferta.prazo_dias} dias."]
    for alternativa in validas:
        sinal = sinal_preco(alternativa.oferta)
        if sinal is not None:
            fatos.append(_frase_sinal(sinal, alternativa.oferta.meses_historico))
    for alternativa in validas[1:]:
        diferenca = alternativa.total_centavos - vencedora.total_centavos
        pontos = variacao_percentual(alternativa.total_centavos, vencedora.total_centavos)
        fatos.append(f"A oferta de {alternativa.oferta.fornecedor_nome} também atende: custa "
                     f"{brl(abs(diferenca))} a {'mais' if diferenca >= 0 else 'menos'} que a recomendada "
                     f"({abs(pontos)} % a {'mais' if diferenca >= 0 else 'menos'}) e entrega em "
                     f"{alternativa.oferta.prazo_dias} dias.")
    return fatos


def aviso_de_preco(resposta: RespostaCompra) -> str | None:
    """Função hardcoded: decide se há algo a avisar e o redige com um modelo de texto fixo.

    Avisa quando o preço do vencedor se afasta da sua média, e aponta uma alternativa válida
    que custa quase o mesmo e está em melhor momento de preço. Se não há nada notável, cala.
    """
    if resposta.estado != "recomendacao":
        return None
    validas = _validas(resposta)
    vencedora = validas[0]
    sinal = sinal_preco(vencedora.oferta)
    if sinal is None:
        return None
    partes = []
    if sinal.nivel != "em linha":
        partes.append(_frase_sinal(sinal, vencedora.oferta.meses_historico))
    if sinal.frente_a_media >= LIMIAR_NOTAVEL:
        for alternativa in validas[1:]:
            outra = sinal_preco(alternativa.oferta)
            pontos = variacao_percentual(alternativa.total_centavos, vencedora.total_centavos)
            if outra is not None and outra.frente_a_media < 0 and 0 <= pontos <= MARGEM_ALTERNATIVA:
                partes.append(f"{alternativa.oferta.fornecedor_nome} custa "
                              f"{brl(alternativa.total_centavos - vencedora.total_centavos)} a mais "
                              f"({pontos} %) e o seu preço está {abs(outra.frente_a_media)} % abaixo "
                              "da sua média.")
                break
    return " ".join(partes) or None


# --- Camada semântica: um conselho redigido pelo modelo e verificado antes de ser publicado. ---

class ConselhoCompra(BaseModel):
    """Conselho breve para o comprador, baseado só nos fatos recebidos."""
    conselho: str = Field(min_length=10, max_length=320,
                          description="Uma ou duas frases; não repete o total nem acrescenta dados novos")


def criar_conselheiro(modelo):
    """Cadeia LCEL: fatos → prompt PTCF com few-shot → modelo → `ConselhoCompra`."""
    from langchain_core.output_parsers import PydanticOutputParser

    from .prompts import MODELO_CONSELHO

    parser = PydanticOutputParser(pydantic_object=ConselhoCompra)
    return MODELO_CONSELHO.partial(formato=parser.get_format_instructions()) | modelo | parser


def _numeros(texto: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)*", texto))


_PREVISAO = (r"\b(garant(?:e|ir|id)|com certeza|sem d[úu]vida|"
             r"(?:cair|baixar|diminuir|subir|aumentar)[áa]|"
             r"(?:vai|v[ãa]o|deve|devem) (?:cair|baixar|diminuir|subir|aumentar))")


def verificar_conselho(conselho: str, fatos: list[str], fornecedores: list[str],
                       classificador: Classificador | None) -> list[str]:
    """Porta do conselho: verificação exata de números e fornecedores, e depois NLI."""
    premissa = " ".join(fatos)
    erros = []
    if _numeros(conselho) - _numeros(premissa):
        erros.append("o conselho contém números que não estão nos fatos")
    nomeados = [f for f in fornecedores if f in conselho]
    if not nomeados:
        erros.append("o conselho não nomeia nenhum fornecedor comparado")
    if re.search(_PREVISAO, conselho, re.I):
        erros.append("o conselho prevê ou garante um preço futuro")
    if erros:
        return erros
    if classificador is None:
        return ["sem classificador NLI"]
    try:
        rotulo = classificador.classificar(premissa, conselho)
    except Exception as exc:
        return [f"NLI indisponível ({type(exc).__name__})"]
    return [] if rotulo == "entailment" else [f"NLI: {rotulo}"]


def aconselhar(resposta: RespostaCompra, conselheiro, classificador: Classificador | None) -> dict:
    """Aviso de preço completo: o aviso fixo e o conselho do modelo, calculados em paralelo.

    Devolve o texto a publicar e um relatório para o rastro. O conselho do modelo substitui
    o aviso fixo só se passar na verificação; se falhar ou não houver modelo, fica o aviso fixo.
    Se não há nada notável a avisar, o modelo não é chamado.
    """
    from langchain_core.runnables import RunnableLambda, RunnableParallel

    aviso = aviso_de_preco(resposta)
    if aviso is None:
        return {"texto": None, "fonte": "nada a avisar"}
    fatos = fatos_de_preco(resposta)
    if conselheiro is None:
        return {"texto": aviso, "fonte": "aviso fixo", "fatos": fatos}
    fornecedores = [a.oferta.fornecedor_nome for a in _validas(resposta)]
    redigir = (RunnableLambda(lambda dado: {"fatos": "\n".join(f"- {f}" for f in dado["fatos"])})
               | conselheiro | RunnableLambda(lambda saida: saida.conselho))
    ramos = RunnableParallel(
        aviso=RunnableLambda(lambda dado: dado["aviso"]),
        conselho=redigir.with_fallbacks([RunnableLambda(lambda dado: None)]))
    saida = ramos.invoke({"fatos": fatos, "aviso": aviso})
    if saida["conselho"] is None:
        return {"texto": aviso, "fonte": "aviso fixo", "fatos": fatos,
                "conselho_rejeitado": None, "erros": ["o modelo não devolveu um conselho válido"]}
    erros = verificar_conselho(saida["conselho"], fatos, fornecedores, classificador)
    if erros:
        return {"texto": aviso, "fonte": "aviso fixo", "fatos": fatos,
                "conselho_rejeitado": saida["conselho"], "erros": erros}
    return {"texto": saida["conselho"], "fonte": "conselho verificado", "fatos": fatos, "erros": []}
