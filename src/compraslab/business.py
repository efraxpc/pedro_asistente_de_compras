"""Decisión de compra determinista; el modelo no calcula importes."""
from .schemas import Alternativa, Oferta, SolicitudCompra


def formatar_brl(centavos: int) -> str:
    """Formato BRL sin pasar por float."""
    reais = f"{centavos // 100:,}".replace(",", ".")
    return f"R$ {reais},{centavos % 100:02d}"


def comparar_ofertas(solicitud: SolicitudCompra, ofertas: list[Oferta]) -> list[Alternativa]:
    faltantes = solicitud.faltantes()
    if faltantes:
        raise ValueError("faltan: " + ", ".join(faltantes))
    resultado = []
    for oferta in ofertas:
        total = solicitud.cantidad * oferta.precio_unitario_centavos + oferta.flete_centavos
        motivos = []
        if oferta.stock < solicitud.cantidad:
            motivos.append("stock")
        if oferta.plazo_dias > solicitud.plazo_max_dias:
            motivos.append("plazo")
        if total > solicitud.presupuesto_centavos:
            motivos.append("presupuesto")
        resultado.append(Alternativa(oferta=oferta, total_centavos=total,
                                     cumple=not motivos, motivos=motivos))
    return sorted(resultado, key=lambda a: (not a.cumple, a.total_centavos,
                                             a.oferta.plazo_dias, a.oferta.proveedor_id))
