"""Dos formas de la misma extracción MVP y composiciones didácticas."""
import json
import re

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough, chain

from .contracts import Extraccion, ExtraccionRazonada
from .prompts import (PLANTILLA_EXTRACCION, PLANTILLA_EXTRACCION_COT,
                      PLANTILLA_EXTRACCION_FEWSHOT, PLANTILLA_REPARACION)

PROMPT = PLANTILLA_EXTRACCION


def _validar(extraccion: Extraccion) -> Extraccion:
    extraccion.faltantes = extraccion.solicitud.faltantes()
    return extraccion


def _json_completo(texto: str) -> bool:
    """Indica si el bloque JSON de la salida está entero (el parser acepta JSON parcial)."""
    bloque = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    try:
        json.loads(bloque.group(1) if bloque else texto)
    except ValueError:
        return False
    return True


def crear_lcel(modelo):
    parser = PydanticOutputParser(pydantic_object=Extraccion)
    return PROMPT.partial(formato=parser.get_format_instructions()) | modelo | parser | RunnableLambda(_validar)


def crear_lcel_robusta(modelo, reparador=None):
    """Extracción con una reparación: si la salida no cumple el esquema, otra cadena la corrige.

    El parser falla con `OutputParserException` tanto por JSON roto como por un dato que
    Pydantic rechaza. El fallback recibe la solicitud, la salida inválida y el error, y
    vuelve a pasar por el mismo parser; si la reparación también falla, el error se propaga.
    """
    parser = PydanticOutputParser(pydantic_object=Extraccion)
    formato = parser.get_format_instructions()
    generar = PROMPT.partial(formato=formato) | modelo | StrOutputParser()

    def analizar_estricto(dato: dict) -> Extraccion:
        extraccion = parser.parse(dato["salida"])
        if not _json_completo(dato["salida"]):
            # El parser tolera JSON cortado y devolvería un objeto al que le faltan datos.
            raise OutputParserException("JSON incompleto: la salida se cortó antes de cerrar")
        return extraccion

    analizar = RunnableLambda(analizar_estricto)
    reparar = (PLANTILLA_REPARACION.partial(formato=formato) | (reparador or modelo)
               | StrOutputParser() | parser)
    return (RunnablePassthrough.assign(salida=generar)
            | analizar.with_fallbacks([reparar], exceptions_to_handle=(OutputParserException,),
                                      exception_key="error")
            | RunnableLambda(_validar))


def crear_chain(modelo):
    lcel = crear_lcel(modelo)

    @chain
    def extraer(dato: dict) -> Extraccion:
        return lcel.invoke(dato)

    return extraer


def crear_chain_robusta(modelo, reparador=None):
    """La misma extracción con reparación, escrita paso a paso con @chain.

    Equivale a `crear_lcel_robusta`: aquí el control de errores es un try/except visible
    en lugar de un `with_fallbacks`.
    """
    parser = PydanticOutputParser(pydantic_object=Extraccion)
    formato = parser.get_format_instructions()
    generar = PROMPT.partial(formato=formato) | modelo | StrOutputParser()
    reparar = PLANTILLA_REPARACION.partial(formato=formato) | (reparador or modelo) | StrOutputParser()

    @chain
    def extraer_con_reparacion(dato: dict) -> Extraccion:
        salida = generar.invoke(dato)
        try:
            extraccion = parser.parse(salida)
            if not _json_completo(salida):
                raise OutputParserException("JSON incompleto: la salida se cortó antes de cerrar")
        except OutputParserException as error:
            corregida = reparar.invoke({"texto": dato["texto"], "salida": salida, "error": error})
            extraccion = parser.parse(corregida)
        return _validar(extraccion)

    return extraer_con_reparacion


def crear_lcel_parcial(modelo):
    """Extracción sin validar que emite el JSON a medida que llega: sirve para `stream()`."""
    from langchain_core.output_parsers import JsonOutputParser

    formato = PydanticOutputParser(pydantic_object=Extraccion).get_format_instructions()
    return PROMPT.partial(formato=formato) | modelo | JsonOutputParser()


def crear_variantes_de_prompt(modelo) -> dict:
    """La misma extracción con tres técnicas de prompt: zero-shot, few-shot y few-shot con CoT."""
    simple = PydanticOutputParser(pydantic_object=Extraccion)
    razonada = PydanticOutputParser(pydantic_object=ExtraccionRazonada)
    return {
        "zero-shot": PROMPT.partial(formato=simple.get_format_instructions()) | modelo | simple,
        "few-shot": (PLANTILLA_EXTRACCION_FEWSHOT.partial(formato=simple.get_format_instructions())
                     | modelo | simple),
        "few-shot + CoT": (PLANTILLA_EXTRACCION_COT.partial(formato=razonada.get_format_instructions())
                           | modelo | razonada),
    }


def composicion_paralela(escenario):
    from .catalog import buscar
    return RunnableParallel({
        "candidatos": RunnableLambda(lambda x: buscar(escenario, x["producto"])),
        "texto": RunnableLambda(lambda x: x["producto"]),
    }) | RunnableLambda(lambda x: {"texto": x["texto"], "cantidad": len(x["candidatos"])})
