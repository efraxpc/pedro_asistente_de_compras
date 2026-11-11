"""Duas formas da mesma extração MVP e composições didáticas."""
import json
import re

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough, chain

from .contracts import Extracao, ExtracaoRaciocinada
from .prompts import (MODELO_EXTRACAO, MODELO_EXTRACAO_COT,
                      MODELO_EXTRACAO_FEWSHOT, MODELO_REPARO)

PROMPT = MODELO_EXTRACAO


def _validar(extracao: Extracao) -> Extracao:
    extracao.faltantes = extracao.solicitacao.faltantes()
    return extracao


def _json_completo(texto: str) -> bool:
    """Indica se o bloco JSON da saída está inteiro (o parser aceita JSON parcial)."""
    bloco = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    try:
        json.loads(bloco.group(1) if bloco else texto)
    except ValueError:
        return False
    return True


def criar_lcel(modelo):
    parser = PydanticOutputParser(pydantic_object=Extracao)
    return PROMPT.partial(formato=parser.get_format_instructions()) | modelo | parser | RunnableLambda(_validar)


def criar_lcel_robusta(modelo, reparador=None):
    """Extração com um reparo: se a saída não atende ao esquema, outra cadeia a corrige.

    O parser falha com `OutputParserException` tanto por JSON quebrado quanto por um dado que
    o Pydantic rejeita. O fallback recebe a solicitação, a saída inválida e o erro, e
    passa de novo pelo mesmo parser; se o reparo também falhar, o erro se propaga.
    """
    parser = PydanticOutputParser(pydantic_object=Extracao)
    formato = parser.get_format_instructions()
    gerar = PROMPT.partial(formato=formato) | modelo | StrOutputParser()

    def analisar_estrito(dado: dict) -> Extracao:
        extracao = parser.parse(dado["saida"])
        if not _json_completo(dado["saida"]):
            # O parser tolera JSON cortado e devolveria um objeto com dados faltando.
            raise OutputParserException("JSON incompleto: a saída foi cortada antes de fechar")
        return extracao

    analisar = RunnableLambda(analisar_estrito)
    reparar = (MODELO_REPARO.partial(formato=formato) | (reparador or modelo)
               | StrOutputParser() | parser)
    return (RunnablePassthrough.assign(saida=gerar)
            | analisar.with_fallbacks([reparar], exceptions_to_handle=(OutputParserException,),
                                      exception_key="erro")
            | RunnableLambda(_validar))


def criar_chain(modelo):
    lcel = criar_lcel(modelo)

    @chain
    def extrair(dado: dict) -> Extracao:
        return lcel.invoke(dado)

    return extrair


def criar_chain_robusta(modelo, reparador=None):
    """A mesma extração com reparo, escrita passo a passo com @chain.

    Equivale a `criar_lcel_robusta`: aqui o controle de erros é um try/except visível
    em vez de um `with_fallbacks`.
    """
    parser = PydanticOutputParser(pydantic_object=Extracao)
    formato = parser.get_format_instructions()
    gerar = PROMPT.partial(formato=formato) | modelo | StrOutputParser()
    reparar = MODELO_REPARO.partial(formato=formato) | (reparador or modelo) | StrOutputParser()

    @chain
    def extrair_com_reparo(dado: dict) -> Extracao:
        saida = gerar.invoke(dado)
        try:
            extracao = parser.parse(saida)
            if not _json_completo(saida):
                raise OutputParserException("JSON incompleto: a saída foi cortada antes de fechar")
        except OutputParserException as erro:
            corrigida = reparar.invoke({"texto": dado["texto"], "saida": saida, "erro": erro})
            extracao = parser.parse(corrigida)
        return _validar(extracao)

    return extrair_com_reparo


def criar_lcel_parcial(modelo):
    """Extração sem validar que emite o JSON à medida que chega: serve para `stream()`."""
    from langchain_core.output_parsers import JsonOutputParser

    formato = PydanticOutputParser(pydantic_object=Extracao).get_format_instructions()
    return PROMPT.partial(formato=formato) | modelo | JsonOutputParser()


def criar_variantes_de_prompt(modelo) -> dict:
    """A mesma extração com três técnicas de prompt: zero-shot, few-shot e few-shot com CoT."""
    simples = PydanticOutputParser(pydantic_object=Extracao)
    raciocinada = PydanticOutputParser(pydantic_object=ExtracaoRaciocinada)
    return {
        "zero-shot": PROMPT.partial(formato=simples.get_format_instructions()) | modelo | simples,
        "few-shot": (MODELO_EXTRACAO_FEWSHOT.partial(formato=simples.get_format_instructions())
                     | modelo | simples),
        "few-shot + CoT": (MODELO_EXTRACAO_COT.partial(formato=raciocinada.get_format_instructions())
                           | modelo | raciocinada),
    }


def composicao_paralela(cenario):
    from .catalog import buscar
    return RunnableParallel({
        "candidatos": RunnableLambda(lambda x: buscar(cenario, x["produto"])),
        "texto": RunnableLambda(lambda x: x["produto"]),
    }) | RunnableLambda(lambda x: {"texto": x["texto"], "quantidade": len(x["candidatos"])})
