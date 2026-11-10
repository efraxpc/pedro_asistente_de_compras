"""Laboratorio de salidas rotas: defectos típicos de un LLM frente a la cadena de extracción."""
import json

from langchain_core.runnables import RunnableLambda

from .chains import crear_lcel_robusta
from .contracts import Extraccion

SOLICITUD = "Compara 2 unidades de PEC-01-0001 hasta R$ 5.000 en 7 días"
DATOS = {"producto_id": "PEC-01-0001", "cantidad": 2,
         "presupuesto_centavos": 500000, "plazo_max_dias": 7}
CORRECTA = {"intencion": "comparar", "faltantes": [], "solicitud": DATOS}


def _variante(intencion: str = "comparar", **solicitud) -> str:
    return json.dumps({"intencion": intencion, "faltantes": [],
                       "solicitud": {**DATOS, **solicitud}}, ensure_ascii=False)


# nombre -> (salida del modelo, capa que debe resolverla)
SALIDAS_ROTAS: dict[str, tuple[str, str]] = {
    "JSON válido": (_variante(), "ninguna"),
    "cercas markdown y charla": ("Claro, aquí tienes:\n```json\n" + _variante()
                                 + "\n```\nEspero que ayude.", "parser"),
    "JSON truncado": (_variante()[:-12], "reparación"),
    "cantidad en letras": (_variante(cantidad="dos"), "reparación"),
    "cantidad negativa": (_variante(cantidad=-2), "reparación"),
    "intención fuera de la lista": (_variante(intencion="comprar"), "reparación"),
    "texto libre sin JSON": ("No puedo responder en JSON, pero quieres 2 compresores.",
                             "reparación"),
    "faltantes mal declarados": (_variante(cantidad=None), "regla de dominio"),
}


def ensayar(reparador) -> list[dict]:
    """Pasa cada salida rota por la cadena robusta y registra qué capa la resolvió.

    El generador es un doble que emite la salida rota; `reparador` es el modelo que repara
    (real o doble). La capa se deduce de lo observado, no de la etiqueta esperada.
    """
    informe = []
    for nombre, (salida, esperada) in SALIDAS_ROTAS.items():
        reparaciones = []

        def contar(prompt, registro=reparaciones):
            registro.append(1)
            return prompt

        cadena = crear_lcel_robusta(RunnableLambda(lambda _, texto=salida: texto),
                                    RunnableLambda(contar) | reparador)
        try:
            resultado: Extraccion | None = cadena.invoke({"texto": SOLICITUD})
            error = None
        except Exception as exc:
            resultado, error = None, type(exc).__name__
        if error:
            capa = "sin resolver"
        elif reparaciones:
            capa = "reparación"
        elif resultado is not None and resultado.faltantes:
            capa = "regla de dominio"
        elif salida.strip().startswith("{"):
            capa = "ninguna"
        else:
            capa = "parser"
        informe.append({"caso": nombre, "capa_esperada": esperada, "capa_observada": capa,
                        "reparaciones": len(reparaciones), "error": error,
                        "resultado": resultado.model_dump(exclude_none=True) if resultado else None})
    return informe
