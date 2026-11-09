"""Reglas exactas en centavos: un flete y sin dividir pedidos."""
from typing import Literal

from .contracts import Alternativa, Oferta, Solicitud


def brl(centavos: int) -> str:
    return f"R$ {centavos // 100:,}".replace(",", ".") + f",{centavos % 100:02d}"


def comparar(solicitud: Solicitud, ofertas: list[Oferta]) -> list[Alternativa]:
    if solicitud.faltantes():
        raise ValueError("faltan: " + ", ".join(solicitud.faltantes()))
    assert solicitud.cantidad is not None
    resultado = []
    for oferta in ofertas:
        total = solicitud.cantidad * oferta.precio_unitario_centavos + oferta.flete_centavos
        motivos: list[Literal["stock", "plazo", "presupuesto"]] = []
        if oferta.stock < solicitud.cantidad:
            motivos.append("stock")
        if solicitud.plazo_max_dias is not None and oferta.plazo_dias > solicitud.plazo_max_dias:
            motivos.append("plazo")
        if solicitud.presupuesto_centavos is not None and total > solicitud.presupuesto_centavos:
            motivos.append("presupuesto")
        resultado.append(Alternativa(oferta=oferta, total_centavos=total,
                                     cumple=not motivos, motivos=motivos))
    return sorted(resultado, key=lambda a: (not a.cumple, a.total_centavos,
                                             a.oferta.plazo_dias, a.oferta.proveedor_id))
