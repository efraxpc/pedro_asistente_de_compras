"""Clasificación NLI local triclase con revisión fijada."""
from typing import Protocol

from .contracts import RespuestaCompra

MODELO = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
REVISION = "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"


class Clasificador(Protocol):
    def clasificar(self, premisa: str, hipotesis: str) -> str: ...


class ModeloNLI:
    def __init__(self):
        from transformers import pipeline
        self._pipe = pipeline("text-classification", model=MODELO, tokenizer=MODELO,
                              revision=REVISION, top_k=None)

    def clasificar(self, premisa: str, hipotesis: str) -> str:
        etiquetas = self._pipe({"text": premisa, "text_pair": hipotesis})
        if etiquetas and isinstance(etiquetas[0], list):
            etiquetas = etiquetas[0]
        ganadora = max(etiquetas, key=lambda x: x["score"])["label"].lower()
        return ganadora if ganadora in {"entailment", "neutral", "contradiction"} else "neutral"


def verificar_nli(respuesta: RespuestaCompra, clasificador: Clasificador) -> bool:
    if respuesta.estado == "politica":
        premisa = "\n".join(e.texto for e in respuesta.evidencias if e.tipo == "politica")
        if not premisa or not respuesta.mensaje:
            return False
        try:
            return clasificador.clasificar(premisa, respuesta.mensaje) == "entailment"
        except Exception:
            return False
    if respuesta.estado != "recomendacion":
        return True
    ganadora = next((a for a in respuesta.alternativas
                     if a.oferta.proveedor_id == respuesta.proveedor_id), None)
    if ganadora is None:
        return False
    fuentes = [e.texto for e in respuesta.evidencias if e.tipo == "catalogo"
               and e.dataset_id == respuesta.dataset_id and e.fuente_id == ganadora.oferta.id]
    if not fuentes:
        return False
    hipotesis = (f"{ganadora.oferta.proveedor_nombre} tiene stock {ganadora.oferta.stock} "
                 f"y entrega en {ganadora.oferta.plazo_dias} días")
    try:
        return clasificador.clasificar("\n".join(fuentes), hipotesis) == "entailment"
    except Exception:
        return False
