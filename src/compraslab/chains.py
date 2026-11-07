"""Demostraciones ejecutables de las APIs del curso sin credenciales."""
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, chain

from .schemas import SolicitudCompra


PROMPT_TEXTO = PromptTemplate.from_template("Compra ficticia: {solicitud}")
PROMPT_CHAT = ChatPromptTemplate.from_messages([
    ("system", "Persona: Pedro, asistente de compras ficticias. Task: aclarar, consultar, comparar y explicar. "
               "Context: catálogo activo y fuentes. Format: JSON validado."),
    ("human", "{solicitud}"),
])


@chain
def faltantes(solicitud: SolicitudCompra) -> list[str]:
    return solicitud.faltantes()


def cadena_demo():
    return RunnableLambda(lambda dato: SolicitudCompra.model_validate(dato)) | faltantes


def parsers_demo():
    return JsonOutputParser(), PydanticOutputParser(pydantic_object=SolicitudCompra)


def composicion_demo():
    """Ramas independientes en paralelo y formato secuencial posterior."""
    paralelo = RunnableParallel({
        "faltantes": cadena_demo(),
        "producto": RunnableLambda(lambda dato: dato.get("producto") or dato.get("producto_id")),
    })
    return paralelo | RunnableLambda(lambda r: f"{r['producto']}: faltan {', '.join(r['faltantes'])}")
