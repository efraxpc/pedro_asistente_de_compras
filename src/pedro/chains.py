"""Dos formas de la misma extracción MVP y composiciones didácticas."""
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel, chain

from .contracts import Extraccion
from .prompts import PLANTILLA_EXTRACCION

PROMPT = PLANTILLA_EXTRACCION


def _validar(extraccion: Extraccion) -> Extraccion:
    extraccion.faltantes = extraccion.solicitud.faltantes()
    return extraccion


def crear_lcel(modelo):
    parser = PydanticOutputParser(pydantic_object=Extraccion)
    return PROMPT.partial(formato=parser.get_format_instructions()) | modelo | parser | RunnableLambda(_validar)


def crear_chain(modelo):
    lcel = crear_lcel(modelo)

    @chain
    def extraer(dato: dict) -> Extraccion:
        return lcel.invoke(dato)

    return extraer


def composicion_paralela(escenario):
    from .catalog import buscar
    return RunnableParallel({
        "candidatos": RunnableLambda(lambda x: buscar(escenario, x["producto"])),
        "texto": RunnableLambda(lambda x: x["producto"]),
    }) | RunnableLambda(lambda x: {"texto": x["texto"], "cantidad": len(x["candidatos"])})
