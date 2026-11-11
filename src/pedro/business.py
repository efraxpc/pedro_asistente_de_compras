"""Reglas exactas en centavos: un flete, sin dividir pedidos y respetando el pedido mínimo."""
from fractions import Fraction
from typing import Literal

from .contracts import Alternativa, Oferta, Solicitud


def brl(centavos: int) -> str:
    return f"R$ {centavos // 100:,}".replace(",", ".") + f",{centavos % 100:02d}"


ETIQUETAS_MOTIVO = {"stock": "stock", "pedido_minimo": "pedido mínimo", "plazo": "plazo",
                    "presupuesto": "presupuesto"}


def describir_motivos(alternativa: Alternativa) -> str:
    """Motivos de descarte en texto, con el dato que los explica cuando ayuda."""
    partes = []
    for motivo in alternativa.motivos:
        if motivo == "pedido_minimo":
            partes.append(f"pedido mínimo ({alternativa.oferta.pedido_minimo} unidades)")
        else:
            partes.append(ETIQUETAS_MOTIVO[motivo])
    return ", ".join(partes)


def variacion_porcentual(actual: int, referencia: int) -> int:
    """Variación de `actual` respecto a `referencia`, en puntos porcentuales enteros."""
    return round(Fraction(100 * (actual - referencia), referencia))


def describir_precio(oferta: Oferta) -> str | None:
    """Sitúa el precio unitario vigente en su historial. No cambia la recomendación."""
    if not oferta.meses_historial or not oferta.precio_medio_centavos or not oferta.precio_anterior_centavos:
        return None
    actual = oferta.precio_unitario_centavos

    def cambio(referencia: int) -> str:
        puntos = variacion_porcentual(actual, referencia)
        return "igual" if puntos == 0 else f"{puntos:+d} %"

    texto = (f"{oferta.proveedor_nombre}: hoy {brl(actual)} por unidad; mes anterior "
             f"{brl(oferta.precio_anterior_centavos)} ({cambio(oferta.precio_anterior_centavos)}); "
             f"media de {oferta.meses_historial} meses {brl(oferta.precio_medio_centavos)} "
             f"({cambio(oferta.precio_medio_centavos)})")
    if actual == oferta.precio_minimo_centavos:
        texto += "; es su precio más bajo del periodo"
    elif actual == oferta.precio_maximo_centavos:
        texto += "; es su precio más alto del periodo"
    return texto + "."


def origen_preferido(preferencias: dict[str, str]) -> Literal["nacional", "internacional"] | None:
    """Traduce la preferencia guardada sobre proveedores a un criterio de comparación."""
    valor = " ".join(v for k, v in preferencias.items() if "proveedor" in k.lower()).lower()
    if "internacional" in valor or "extranjer" in valor or "importad" in valor:
        return "internacional"
    if "nacional" in valor or "local" in valor or "brasil" in valor:
        return "nacional"
    return None


def comparar(solicitud: Solicitud, ofertas: list[Oferta]) -> list[Alternativa]:
    """Evalúa cada oferta y las ordena: primero las que cumplen; entre ellas, las del origen
    que prefiere el usuario; después, por total, plazo y proveedor."""
    if solicitud.faltantes():
        raise ValueError("faltan: " + ", ".join(solicitud.faltantes()))
    assert solicitud.cantidad is not None
    resultado = []
    for oferta in ofertas:
        total = solicitud.cantidad * oferta.precio_unitario_centavos + oferta.flete_centavos
        motivos: list[Literal["stock", "pedido_minimo", "plazo", "presupuesto"]] = []
        if oferta.stock < solicitud.cantidad:
            motivos.append("stock")
        if solicitud.cantidad < oferta.pedido_minimo:
            motivos.append("pedido_minimo")
        if solicitud.plazo_max_dias is not None and oferta.plazo_dias > solicitud.plazo_max_dias:
            motivos.append("plazo")
        if solicitud.presupuesto_centavos is not None and total > solicitud.presupuesto_centavos:
            motivos.append("presupuesto")
        resultado.append(Alternativa(oferta=oferta, total_centavos=total,
                                     cumple=not motivos, motivos=motivos))
    preferido = solicitud.origen_preferido

    def fuera_de_preferencia(alternativa: Alternativa) -> bool:
        return preferido is not None and alternativa.oferta.nacional != (preferido == "nacional")

    return sorted(resultado, key=lambda a: (not a.cumple, fuera_de_preferencia(a), a.total_centavos,
                                             a.oferta.plazo_dias, a.oferta.proveedor_id))
