"""Laboratorio de salidas rotas: defectos típicos de un LLM frente a la cadena de extracción."""
import json

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableLambda

from .chains import crear_chain_robusta, crear_lcel_robusta
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


def ensayar(reparador, constructor=crear_lcel_robusta) -> list[dict]:
    """Pasa cada salida rota por la cadena robusta y registra qué capa la resolvió.

    El generador es un doble que emite la salida rota; `reparador` es el modelo que repara
    (real o doble). `constructor` elige la cadena: declarativa o imperativa. La capa se
    deduce de lo observado, no de la etiqueta esperada.
    """
    informe = []
    for nombre, (salida, esperada) in SALIDAS_ROTAS.items():
        reparaciones = []

        def contar(prompt, registro=reparaciones):
            registro.append(1)
            return prompt

        cadena = constructor(RunnableLambda(lambda _, texto=salida: texto),
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


class _PasosTrazados(BaseCallbackHandler):
    """Anota cada paso que la traza de LangChain llega a ver."""

    def __init__(self):
        self.pasos: list[str] = []

    def on_chain_start(self, serialized, inputs, *, name=None, **kwargs) -> None:
        self.pasos.append(name or "paso")

    def on_chain_error(self, error, **kwargs) -> None:
        self.pasos.append("ERROR:" + type(error).__name__)


def comparar_estilos() -> dict[str, dict]:
    """Mide lo que deja ver cada estilo de la misma cadena con reparación.

    Usa dobles: no llama a ningún modelo. Ejecuta un caso sin fallo y otro con reparación
    y cuenta los pasos que registra la traza y los nodos del grafo.
    """
    correcta = json.dumps(CORRECTA)
    reparador = RunnableLambda(lambda _: correcta)
    medidas = {}
    for estilo, constructor in (("declarativa (LCEL)", crear_lcel_robusta),
                                ("imperativa (@chain)", crear_chain_robusta)):
        registro = {}
        for caso, salida in (("sin_fallo", correcta),
                             ("con_reparacion", SALIDAS_ROTAS["cantidad negativa"][0])):
            traza = _PasosTrazados()
            cadena = constructor(RunnableLambda(lambda _, texto=salida: texto), reparador)
            resultado = cadena.invoke({"texto": SOLICITUD}, config={"callbacks": [traza]})
            registro[caso] = {"pasos": traza.pasos, "cantidad": resultado.solicitud.cantidad}
        nodos = [nodo.name for nodo in cadena.get_graph().nodes.values()]
        medidas[estilo] = {
            "pasos_trazados_sin_fallo": len(registro["sin_fallo"]["pasos"]),
            "pasos_trazados_con_reparacion": len(registro["con_reparacion"]["pasos"]),
            "el_error_queda_en_la_traza": any(
                paso.startswith("ERROR") for paso in registro["con_reparacion"]["pasos"]),
            "la_validacion_de_dominio_queda_en_la_traza": "_validar" in registro["sin_fallo"]["pasos"],
            "el_grafo_muestra_la_reparacion": "WithFallbacks" in nodos,
            "resultado_tras_reparar": registro["con_reparacion"]["cantidad"],
            "pasos_con_reparacion": registro["con_reparacion"]["pasos"],
        }
    return medidas
