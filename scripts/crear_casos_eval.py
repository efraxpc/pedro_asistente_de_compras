"""Congela 30 referencias derivadas del catálogo, sin usar el comparador del agente.

La regla de referencia incluye el pedido mínimo de cada oferta.
"""
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUENTE = ROOT / "datasets/piezas_electrodomesticos.sqlite3"
DESTINO = ROOT / "evals/casos_derivados.json"


def brl(centavos):
    return f"R$ {centavos // 100:,}".replace(",", ".") + f",{centavos % 100:02d}"


casos = []
candidatos = [f"PEC-{categoria:02d}-0001" for categoria in range(1, 12)]
candidatos += [f"PEC-{categoria:02d}-0002" for categoria in range(1, 12)]
bloqueados_por_minimo = []
with sqlite3.connect(FUENTE) as db:
    for producto_id in candidatos:
        filas = db.execute(
            "SELECT o.id,o.supplier_id,o.estimated_brl_cents,o.shipping_brl_cents,"
            "o.stock_qty,o.lead_days,o.min_order_qty FROM offers o WHERE o.part_id=?",
            (producto_id,)).fetchall()
        # Regla de referencia, escrita aquí aparte: stock suficiente, pedido mínimo cumplido,
        # plazo y presupuesto dentro de los límites; gana el menor total.
        validas = [(2 * precio + flete, plazo, proveedor, oferta)
                   for oferta, proveedor, precio, flete, stock, plazo, minimo in filas
                   if stock >= 2 and minimo <= 2 and plazo <= 60 and 2 * precio + flete <= 10_000_000]
        if not validas:
            con_stock = any(stock >= 2 and plazo <= 60 for *_, stock, plazo, _ in filas)
            if con_stock:
                bloqueados_por_minimo.append(producto_id)
            continue
        if sum(c["grupo"] == "recomendacion" for c in casos) == 14:
            continue
        total, _, proveedor, oferta = min(validas)
        casos.append({
            "id": f"rec-{len(casos)+1:02d}", "grupo": "recomendacion",
            "pregunta": (f"Compara 2 unidades de {producto_id}; presupuesto R$ 100000 "
                         "y plazo máximo 60 días."),
            "esperado": {"estado": "recomendacion", "ganador": proveedor,
                         "total_centavos": total, "total_brl": brl(total),
                         "fuente_ganadora": oferta,
                         "herramientas": ["consultar_catalogo", "comparar_ofertas"]},
        })
if sum(c["grupo"] == "recomendacion" for c in casos) != 14 or len(bloqueados_por_minimo) < 3:
    raise RuntimeError("no hay suficientes referencias")

# Sin oferta: dos por cantidad imposible y tres porque ningún proveedor acepta un pedido de 2.
for producto_id, cantidad in [(candidatos[0], 1000), (candidatos[1], 1000),
                              *[(producto_id, 2) for producto_id in bloqueados_por_minimo[:3]]]:
    casos.append({
        "id": f"sin-{len(casos)+1:02d}", "grupo": "sin_oferta",
        "pregunta": (f"Compara {cantidad} unidades de {producto_id}; presupuesto R$ 100000 "
                     "y plazo máximo 60 días."),
        "esperado": {"estado": "sin_oferta", "contiene": "Ninguna oferta",
                     "herramientas": ["consultar_catalogo", "comparar_ofertas"]},
    })

for pregunta in [
    "Quiero PEC-01-0001.",
    "Compara PEC-02-0001 con presupuesto R$ 100000 y plazo 60 días.",
    "Necesito 2 repuestos con presupuesto R$ 100000 y plazo 60 días. ¿Cuál pieza?",
    "Quiero comparar ofertas, pero aún no sé la pieza ni la cantidad.",
]:
    casos.append({"id": f"acl-{len(casos)+1:02d}", "grupo": "aclaracion",
                  "pregunta": pregunta,
                  "esperado": {"estado": "aclaracion", "contiene": "¿",
                               "herramientas": []}})

for pregunta, contiene in [
    ("lista piezas", "PEC-01-0001"),
    ("lista piezas página 2", "PEC-01-0021"),
    ("ficha PEC-01-0001", "PEC-01-0001"),
]:
    casos.append({"id": f"cat-{len(casos)+1:02d}", "grupo": "catalogo",
                  "pregunta": pregunta,
                  "esperado": {"estado": "catalogo", "contiene": contiene, "herramientas": []}})

for pregunta in ["Consulta el CEP 01001000", "¿A qué ciudad corresponde 01001000?"]:
    casos.append({"id": f"cep-{len(casos)+1:02d}", "grupo": "cep",
                  "pregunta": pregunta,
                  "esperado": {"estado": "cep", "contiene": "São Paulo/SP",
                               "herramientas": ["consultar_cep"]}})

for pregunta in ["¿Qué dice la política de devoluciones?", "¿Hay política de cambios?"]:
    casos.append({"id": f"pol-{len(casos)+1:02d}", "grupo": "politica_sin_indice",
                  "pregunta": pregunta,
                  "esperado": {"estado": "sin_evidencia", "contiene": "No puedo confirmar",
                               "herramientas": ["consultar_politicas"]}})

assert len(casos) == 30
DESTINO.write_text(json.dumps({
    "tipo": "derivados_sinteticos_no_oficiales",
    "fuente_sha256": hashlib.sha256(FUENTE.read_bytes()).hexdigest(),
    "casos": casos,
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(DESTINO, len(casos))
