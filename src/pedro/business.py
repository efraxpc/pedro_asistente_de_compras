"""Reglas exactas en centavos: un flete, sin dividir pedidos y respetando el pedido mínimo."""
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
