"""Completa una solicitud por turnos sin inventar restricciones comerciales."""
import re
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field

from .catalog import Escenario, buscar, ficha
from .contracts import Solicitud

PALABRAS_IGNORADAS = {"ahora", "busco", "comparar", "compara", "comprar", "cuanto",
                     "cuesta", "dias", "días", "hasta", "necesito", "oferta", "ofertas",
                     "para", "pieza", "piezas", "plazo", "precio", "presupuesto",
                     "quiero", "recomienda", "repuesto", "repuestos", "unidades"}


class EstadoCompra(BaseModel):
    solicitud: Solicitud = Field(default_factory=Solicitud)
    esperando: Literal["producto", "cantidad"] | None = None


def _centavos(valor: str) -> int | None:
    numero = valor.strip()
    if "," in numero:
        numero = numero.replace(".", "").replace(",", ".")
    elif "." in numero and len(numero.rsplit(".", 1)[1]) == 3:
        numero = numero.replace(".", "")
    try:
        decimal = Decimal(numero)
    except InvalidOperation:
        return None
    if not decimal.is_finite() or decimal < 0 or int(decimal.as_tuple().exponent) < -2:
        return None
    return int(decimal * 100)


def _cantidad(texto: str, esperando: str | None) -> int | None:
    numero = r"(\d+)"
    patrones = (
        rf"\b{numero}\s*(?:unidad(?:es)?|piezas?|repuestos?)\b",
        rf"\bcantidad(?:\s+(?:de|a))?\s*[:=]?\s*{numero}\b",
        rf"\b(?:ahora|quiero|necesito|compara|comparar|son|ser[ií]an?)\s+{numero}\b",
        # Cambios dichos de pasada: «que sean 3», «mejor 4», «cambia a 5».
        rf"\b(?:sean|mejor|cambia(?:r)?\s+a|sube(?:r)?\s+a|baja(?:r)?\s+a)\s+{numero}\b"
        r"(?!\s*(?:d[ií]as?|semanas?|reales|mil)\b|[.,]\d)",
    )
    for patron in patrones:
        if coincidencia := re.search(patron, texto, re.I):
            return int(coincidencia.group(1))
    if esperando == "cantidad" and (coincidencia := re.fullmatch(
            r"\s*(\d+)\s*(?:unidad(?:es)?|piezas?|repuestos?)?"
            r"\s*(?:,?\s*por favor)?[.!]?\s*", texto, re.I)):
        return int(coincidencia.group(1))
    if re.search(r"\bmedia\s+docena\b", texto, re.I):
        return 6
    if re.search(r"\buna\s+docena\b", texto, re.I):
        return 12
    if re.search(r"\bun\s+par\b", texto, re.I):
        return 2
    palabras = {"una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
                "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}
    nombres = "|".join(palabras)
    if coincidencia := re.search(rf"\b({nombres})\s+(?:unidad(?:es)?|piezas?|repuestos?)\b",
                                 texto, re.I):
        return palabras[coincidencia.group(1).lower()]
    if coincidencia := re.search(rf"\b(?:ahora|sean|mejor|cantidad\s+(?:de|a)?)\s*({nombres})\b"
                                 r"(?!\s*(?:d[ií]as?|semanas?)\b)", texto, re.I):
        return palabras[coincidencia.group(1).lower()]
    if esperando == "cantidad" and texto.lower().strip(" .!") in palabras:
        return palabras[texto.lower().strip(" .!")]
    if re.search(r"\bprecio\s+unitario\b|\bprecio\s+de\b", texto, re.I):
        return 1
    return None


def _candidatos(escenario: Escenario, texto: str) -> list[dict]:
    tokens = [x for x in re.findall(r"[\w-]{4,}", texto.lower())
              if x not in PALABRAS_IGNORADAS and not x.isdigit()]
    resultados = [buscar(escenario, token, 4) for token in tokens]
    resultados = [x for x in resultados if x]
    return min(resultados, key=len) if resultados else []


def interpretar_compra(escenario: Escenario, previo: EstadoCompra | None,
                       mensaje: str) -> tuple[EstadoCompra, str | None] | None:
    """Devuelve un borrador y, si falta una decisión, una pregunta concreta."""
    texto = mensaje.strip()
    # Preguntas que no son una compra: CEP, políticas y preferencias van al agente.
    if re.search(r"\b(cep|pol[ií]ticas?|devoluci[oó]n|devolver|garant[ií]a|reembolso|compatibilidad|"
                 r"instalar|instalaci[oó]n|preferencia|prefiero|recuerda|recu[eé]rda(?:lo|me)|guarda)\b",
                 texto, re.I):
        return None
    ids = re.findall(r"\bPEC-[0-9]{2}-[0-9]{4}\b", texto.upper())
    intencion = bool(re.search(r"\b(quiero|necesito|compara|comparar|recomienda|cotiza|"
                               r"comprar|precio|ofertas?)\b", texto, re.I))
    seguimiento = previo is not None and bool(re.search(
        r"\b(ahora|cambia|cambiar|mismo|mant[eé]n|cantidad|plazo|presupuesto|sean|mejor|"
        r"vuelve|de\s+nuevo|otra\s+vez)\b|\b\d+\s*(?:unidad(?:es)?|piezas?|repuestos?)\b|R\$",
        texto, re.I))
    if previo is not None and previo.esperando is not None:
        seguimiento = True
    if not intencion and not seguimiento and not ids:
        return None

    solicitud = previo.solicitud.model_copy(deep=True) if previo else Solicitud()
    esperando = previo.esperando if previo else None
    if len(set(ids)) > 1:
        return EstadoCompra(solicitud=solicitud, esperando="producto"), (
            "¿Cuál de esos IDs quieres comparar? Indica uno solo.")
    if ids:
        producto_id = ids[0]
        if ficha(escenario, producto_id) is None:
            return EstadoCompra(solicitud=solicitud, esperando="producto"), (
                f"No encontré {producto_id} en este escenario. Indica otro ID o SKU.")
        if solicitud.producto_id != producto_id and not re.search(r"\b(mismo|mant[eé]n)\b", texto, re.I):
            solicitud = Solicitud()
        solicitud.producto_id = producto_id
        solicitud.producto = None
    elif re.search(r"\b(otra|otro)\s+(?:pieza|repuesto|producto)\b", texto, re.I):
        solicitud = Solicitud()
    elif solicitud.producto_id is None:
        candidatos = _candidatos(escenario, texto)
        if len(candidatos) == 1:
            solicitud.producto_id = candidatos[0]["id"]
        elif candidatos:
            opciones = ", ".join(f"{c['id']} ({c['sku']})" for c in candidatos[:4])
            return EstadoCompra(solicitud=solicitud, esperando="producto"), (
                f"Encontré varias piezas. ¿Cuál necesitas? {opciones}.")

    cantidad = _cantidad(texto, esperando)
    if cantidad is not None:
        if cantidad < 1:
            return EstadoCompra(solicitud=solicitud, esperando="cantidad"), (
                "¿Cuántas unidades necesitas? Debe ser al menos una.")
        solicitud.cantidad = cantidad

    if re.search(r"\b(sin|no\s+tengo)\s+(?:l[ií]mite\s+de\s+)?presupuesto\b", texto, re.I):
        solicitud.presupuesto_centavos = None
    elif coincidencia := re.search(r"(?:R\$\s*|presupuesto(?:\s+m[aá]ximo)?\s*(?:de\s*)?)"
                                   r"(\d[\d.,]*)", texto, re.I):
        if (valor := _centavos(coincidencia.group(1))) is not None:
            solicitud.presupuesto_centavos = valor

    if re.search(r"\b(sin|no\s+tengo)\s+(?:l[ií]mite\s+de\s+)?plazo\b", texto, re.I):
        solicitud.plazo_max_dias = None
    elif coincidencia := re.search(r"\b(\d+)\s*d[ií]as\b|\bplazo(?:\s+m[aá]ximo)?"
                                   r"\s*(?:de\s*)?(\d+)\b", texto, re.I):
        solicitud.plazo_max_dias = int(coincidencia.group(1) or coincidencia.group(2))

    if solicitud.producto_id is None:
        return EstadoCompra(solicitud=solicitud, esperando="producto"), (
            "¿Qué pieza necesitas? Indica su ID o SKU; puedo buscarla por nombre.")
    if solicitud.cantidad is None:
        return EstadoCompra(solicitud=solicitud, esperando="cantidad"), (
            f"¿Cuántas unidades de {solicitud.producto_id} necesitas? "
            "Puedo comparar sin presupuesto o plazo máximo si no tienes esos límites.")
    return EstadoCompra(solicitud=solicitud, esperando=None), None
