"""Aviso de precio: sitúa el precio de hoy en su historial y aconseja con respaldo.

Dos capas, como en el resto del asistente:
- Hardcoded: la señal de cada oferta y el aviso se calculan con umbrales fijos.
- Semántica: un modelo redacta un consejo a partir de esos hechos, y solo se publica si sus
  cifras salen de los hechos y un modelo NLI confirma que los hechos lo respaldan.
El aviso informa al comprador; no cambia qué oferta gana.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

from .business import brl, variacion_porcentual
from .contracts import Alternativa, Oferta, RespuestaCompra
from .nli import Clasificador

UMBRAL_NOTABLE = 10    # puntos porcentuales frente a la media: por encima o por debajo
UMBRAL_FUERTE = 20    # muy por encima o muy por debajo
MARGEN_ALTERNATIVA = 5  # una alternativa «cuesta casi lo mismo» si su total supera al ganador en ≤ 5 %
Nivel = Literal["muy por encima", "por encima", "en línea", "por debajo", "muy por debajo"]


class SenalPrecio(BaseModel):
    """Dónde está el precio unitario de hoy respecto a su historial."""
    proveedor: str
    nivel: Nivel
    frente_a_media: int   # puntos porcentuales
    frente_a_mes_anterior: int
    en_minimo: bool
    en_maximo: bool


def senal_precio(oferta: Oferta) -> SenalPrecio | None:
    """Función hardcoded: clasifica el precio de hoy con umbrales fijos."""
    if not oferta.precio_medio_centavos or not oferta.precio_anterior_centavos:
        return None
    actual = oferta.precio_unitario_centavos
    puntos = variacion_porcentual(actual, oferta.precio_medio_centavos)
    if puntos >= UMBRAL_FUERTE:
        nivel: Nivel = "muy por encima"
    elif puntos >= UMBRAL_NOTABLE:
        nivel = "por encima"
    elif puntos <= -UMBRAL_FUERTE:
        nivel = "muy por debajo"
    elif puntos <= -UMBRAL_NOTABLE:
        nivel = "por debajo"
    else:
        nivel = "en línea"
    return SenalPrecio(proveedor=oferta.proveedor_nombre, nivel=nivel, frente_a_media=puntos,
                       frente_a_mes_anterior=variacion_porcentual(actual, oferta.precio_anterior_centavos),
                       en_minimo=actual == oferta.precio_minimo_centavos,
                       en_maximo=actual == oferta.precio_maximo_centavos)


def _validas(respuesta: RespuestaCompra) -> list[Alternativa]:
    return [a for a in respuesta.alternativas if a.cumple]


def _frase_senal(senal: SenalPrecio, meses: int) -> str:
    if senal.nivel == "en línea":
        frase = f"El precio de {senal.proveedor} está en línea con su media de {meses} meses"
    else:
        frase = (f"El precio de {senal.proveedor} está {abs(senal.frente_a_media)} % "
                 f"{'por encima' if senal.frente_a_media > 0 else 'por debajo'} de su media de {meses} meses")
    if senal.en_minimo:
        frase += " y es el más bajo del periodo"
    elif senal.en_maximo:
        frase += " y es el más alto del periodo"
    return frase + "."


def hechos_de_precio(respuesta: RespuestaCompra) -> list[str]:
    """Hechos comprobables sobre los precios, en frases. Son la premisa del consejo."""
    if respuesta.estado != "recomendacion":
        return []
    validas = _validas(respuesta)
    ganadora = validas[0]
    hechos = [f"La oferta recomendada es la de {ganadora.oferta.proveedor_nombre}, con un total de "
              f"{brl(ganadora.total_centavos)} y entrega en {ganadora.oferta.plazo_dias} días."]
    for alternativa in validas:
        senal = senal_precio(alternativa.oferta)
        if senal is not None:
            hechos.append(_frase_senal(senal, alternativa.oferta.meses_historial))
    for alternativa in validas[1:]:
        diferencia = alternativa.total_centavos - ganadora.total_centavos
        puntos = variacion_porcentual(alternativa.total_centavos, ganadora.total_centavos)
        hechos.append(f"La oferta de {alternativa.oferta.proveedor_nombre} también cumple: cuesta "
                      f"{brl(abs(diferencia))} {'más' if diferencia >= 0 else 'menos'} que la recomendada "
                      f"({abs(puntos)} % {'más' if diferencia >= 0 else 'menos'}) y entrega en "
                      f"{alternativa.oferta.plazo_dias} días.")
    return hechos


def aviso_de_precio(respuesta: RespuestaCompra) -> str | None:
    """Función hardcoded: decide si hay algo que avisar y lo redacta con una plantilla fija.

    Avisa cuando el precio del ganador se aparta de su media, y señala una alternativa válida
    que cuesta casi lo mismo y tiene mejor momento de precio. Si no hay nada notable, calla.
    """
    if respuesta.estado != "recomendacion":
        return None
    validas = _validas(respuesta)
    ganadora = validas[0]
    senal = senal_precio(ganadora.oferta)
    if senal is None:
        return None
    partes = []
    if senal.nivel != "en línea":
        partes.append(_frase_senal(senal, ganadora.oferta.meses_historial))
    if senal.frente_a_media >= UMBRAL_NOTABLE:
        for alternativa in validas[1:]:
            otra = senal_precio(alternativa.oferta)
            puntos = variacion_porcentual(alternativa.total_centavos, ganadora.total_centavos)
            if otra is not None and otra.frente_a_media < 0 and 0 <= puntos <= MARGEN_ALTERNATIVA:
                partes.append(f"{alternativa.oferta.proveedor_nombre} cuesta "
                              f"{brl(alternativa.total_centavos - ganadora.total_centavos)} más "
                              f"({puntos} %) y su precio está {abs(otra.frente_a_media)} % por debajo "
                              "de su media.")
                break
    return " ".join(partes) or None


# --- Capa semántica: un consejo redactado por el modelo y verificado antes de publicarse. ---

class ConsejoCompra(BaseModel):
    """Consejo breve para el comprador, basado solo en los hechos recibidos."""
    consejo: str = Field(min_length=10, max_length=320,
                         description="Una o dos frases; no repite el total ni añade datos nuevos")


def crear_consejero(modelo):
    """Cadena LCEL: hechos → prompt PTCF con few-shot → modelo → `ConsejoCompra`."""
    from langchain_core.output_parsers import PydanticOutputParser

    from .prompts import PLANTILLA_CONSEJO

    parser = PydanticOutputParser(pydantic_object=ConsejoCompra)
    return PLANTILLA_CONSEJO.partial(formato=parser.get_format_instructions()) | modelo | parser


def _cifras(texto: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)*", texto))


def verificar_consejo(consejo: str, hechos: list[str], proveedores: list[str],
                      clasificador: Clasificador | None) -> list[str]:
    """Puerta del consejo: verificación exacta de cifras y proveedores, y después NLI."""
    premisa = " ".join(hechos)
    errores = []
    if _cifras(consejo) - _cifras(premisa):
        errores.append("el consejo contiene cifras que no están en los hechos")
    nombrados = [p for p in proveedores if p in consejo]
    if not nombrados:
        errores.append("el consejo no nombra a ningún proveedor comparado")
    if re.search(r"\b(garantiz|seguro que|sin duda|bajar[áa]|subir[áa]|va a (bajar|subir))", consejo, re.I):
        errores.append("el consejo predice o garantiza un precio futuro")
    if errores:
        return errores
    if clasificador is None:
        return ["sin clasificador NLI"]
    try:
        etiqueta = clasificador.clasificar(premisa, consejo)
    except Exception as exc:
        return [f"NLI no disponible ({type(exc).__name__})"]
    return [] if etiqueta == "entailment" else [f"NLI: {etiqueta}"]


def aconsejar(respuesta: RespuestaCompra, consejero, clasificador: Clasificador | None) -> dict:
    """Aviso de precio completo: el aviso fijo y el consejo del modelo, calculados en paralelo.

    Devuelve el texto a publicar y un informe para la traza. El consejo del modelo sustituye
    al aviso fijo solo si pasa la verificación; si falla o no hay modelo, queda el aviso fijo.
    Si no hay nada notable que avisar, no se llama al modelo.
    """
    from langchain_core.runnables import RunnableLambda, RunnableParallel

    aviso = aviso_de_precio(respuesta)
    if aviso is None:
        return {"texto": None, "fuente": "nada que avisar"}
    hechos = hechos_de_precio(respuesta)
    if consejero is None:
        return {"texto": aviso, "fuente": "aviso fijo", "hechos": hechos}
    proveedores = [a.oferta.proveedor_nombre for a in _validas(respuesta)]
    redactar = (RunnableLambda(lambda dato: {"hechos": "\n".join(f"- {h}" for h in dato["hechos"])})
                | consejero | RunnableLambda(lambda salida: salida.consejo))
    ramas = RunnableParallel(
        aviso=RunnableLambda(lambda dato: dato["aviso"]),
        consejo=redactar.with_fallbacks([RunnableLambda(lambda dato: None)]))
    salida = ramas.invoke({"hechos": hechos, "aviso": aviso})
    if salida["consejo"] is None:
        return {"texto": aviso, "fuente": "aviso fijo", "hechos": hechos,
                "consejo_rechazado": None, "errores": ["el modelo no devolvió un consejo válido"]}
    errores = verificar_consejo(salida["consejo"], hechos, proveedores, clasificador)
    if errores:
        return {"texto": aviso, "fuente": "aviso fijo", "hechos": hechos,
                "consejo_rechazado": salida["consejo"], "errores": errores}
    return {"texto": salida["consejo"], "fuente": "consejo verificado", "hechos": hechos, "errores": []}
