"""NLI sobre afirmaciones observables; complementa los cálculos exactos."""
from typing import Literal, Protocol

from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate

from .schemas import RespuestaCompra


class EtiquetaNLI(BaseModel):
    etiqueta: Literal["entailment", "contradiction", "neutral"]


class ClasificadorNLI(Protocol):
    def clasificar(self, premisa: str, hipotesis: str) -> str: ...


class NLIConModelo:
    """Clasificador remoto configurado; no afirma equivalencia con un modelo XNLI local."""
    def __init__(self, llm):
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Clasifica la relación entre premisa e hipótesis como entailment, "
                       "contradiction o neutral. Usa solo la premisa. Devuelve la etiqueta."),
            ("human", "Premisa: {premisa}\nHipótesis: {hipotesis}"),
        ])
        self.cadena = prompt | llm.with_structured_output(EtiquetaNLI)

    def clasificar(self, premisa: str, hipotesis: str) -> str:
        return self.cadena.invoke({"premisa": premisa, "hipotesis": hipotesis}).etiqueta


def verificar_nli(respuesta: RespuestaCompra, clasificador: ClasificadorNLI) -> bool:
    """Exige respaldo para proveedor, stock y plazo; total ya se calcula exactamente."""
    if respuesta.estado != "recomendacion":
        return True
    ganadora = next((a for a in respuesta.alternativas
                     if a.oferta.proveedor_id == respuesta.proveedor_id), None)
    if ganadora is None:
        return False
    fuentes = [e for e in respuesta.evidencias if e.tipo == "catalogo"
               and e.dataset_id == respuesta.dataset_id and e.fuente_id == ganadora.oferta.id]
    if not fuentes:
        return False
    premisa = "\n".join(e.texto for e in fuentes)
    hipotesis = (f"{ganadora.oferta.proveedor_nombre} tiene stock {ganadora.oferta.stock} "
                 f"y entrega en {ganadora.oferta.plazo_dias} días.")
    return clasificador.clasificar(premisa, hipotesis) == "entailment"
