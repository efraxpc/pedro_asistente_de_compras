import sqlite3
import runpy
import json
from pathlib import Path

import pytest

from compraslab.agent import responder_consulta_catalogo
from compraslab.data import abrir_catalogo, buscar_productos, crear_catalogo, listar_productos, ofertas_producto
from compraslab.part_catalog import detalle_pieza, listar_piezas
from compraslab.query import text_to_query

generator = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                               "scripts/generar_catalogo_piezas.py"))
CATEGORIES = generator["CATEGORIES"]
generate = generator["generate"]


def test_catalogo_publicado_tiene_integridad_y_cobertura():
    database = Path(__file__).resolve().parents[1] / "datasets/piezas_electrodomesticos.sqlite3"
    with sqlite3.connect(database) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        counts = dict(db.execute("SELECT c.slug, COUNT(*) FROM parts p JOIN categories c "
                                 "ON c.id=p.category_id GROUP BY c.slug"))
        assert counts == {slug: 240 for slug, _, _ in CATEGORIES}
        assert db.execute("SELECT COUNT(*) FROM offers").fetchone()[0] == 7920
        assert db.execute("SELECT COUNT(*) FROM price_history").fetchone()[0] == 47520
        assert db.execute("SELECT COUNT(DISTINCT country_code) FROM suppliers").fetchone()[0] >= 5
        assert db.execute("SELECT COUNT(*) FROM offers WHERE availability='in_stock' "
                          "AND stock_qty=0").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM offers o WHERE NOT EXISTS "
                          "(SELECT 1 FROM price_history h WHERE h.offer_id=o.id "
                          "AND h.observed_on=o.updated_on AND h.unit_price_minor=o.unit_price_minor "
                          "AND h.estimated_brl_cents=o.estimated_brl_cents)").fetchone()[0] == 0


def test_generador_reproduce_precios_y_proveedores(tmp_path):
    first = tmp_path / "a.sqlite3"
    second = tmp_path / "b.sqlite3"
    assert generate(first, pieces_per_category=2, seed=5) == generate(
        second, pieces_per_category=2, seed=5)
    with sqlite3.connect(first) as a, sqlite3.connect(second) as b:
        query = "SELECT id, part_id, supplier_id, unit_price_minor FROM offers ORDER BY id"
        assert a.execute(query).fetchall() == b.execute(query).fetchall()
        assert a.execute("SELECT COUNT(*) FROM parts").fetchone()[0] == 22


def test_escenario_de_piezas_conserva_ofertas_verificables(tmp_path):
    catalogo = crear_catalogo(tmp_path, cantidad=4)
    productos = buscar_productos(catalogo, "PROD-0001")
    assert len(productos) == 1
    assert productos[0].unidad == "pieza"
    assert len(listar_piezas(catalogo)) == 4
    assert len(ofertas_producto(catalogo, "PROD-0001")) == 3
    assert text_to_query(catalogo, "ofertas PROD-0001").estado == "ok"


def test_lectura_completa_de_piezas_y_detalles_desde_sqlite(tmp_path):
    catalogo = crear_catalogo(tmp_path, cantidad=3000)
    piezas = listar_piezas(catalogo)
    assert len(piezas) == 2640
    assert len({p["category"] for p in piezas}) == 11
    assert {p["sku"] for p in piezas} == {p.modelo for p in listar_productos(catalogo)}
    detalle = detalle_pieza(catalogo, piezas[0]["sku"])
    assert detalle["product_id"] == piezas[0]["product_id"]
    assert len(detalle["compatibility"]) == 3
    assert len(detalle["offers"]) == 3
    assert all(len(history) == 6 for history in detalle["price_history"].values())
    assert detalle["technical_specs"]
    assert detalle_pieza(catalogo, "SKU-INEXISTENTE") is None


def test_chat_pagina_catalogo_y_detalle(tmp_path):
    catalogo = crear_catalogo(tmp_path, cantidad=3000)
    primera = responder_consulta_catalogo(catalogo, "Muéstrame todas las piezas")
    segunda = responder_consulta_catalogo(catalogo, "Lista piezas página 2")
    assert "2640 en total; página 1/132" in primera
    assert "2640 en total; página 2/132" in segunda
    assert "Catálogo de piezas" in primera
    assert "240 en total; página 1/12" in responder_consulta_catalogo(
        catalogo, "Lista piezas de neveras")
    assert "fuera de rango" in responder_consulta_catalogo(catalogo, "Lista piezas página 999")
    producto = listar_piezas(catalogo)[0]
    ficha = responder_consulta_catalogo(catalogo, f"Detalle de {producto['product_id']}")
    assert producto["sku"] in ficha
    assert "Ofertas ficticias" in ficha


def test_catalogo_anterior_no_se_reactiva(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"modo": "dummyjson"}))
    with pytest.raises(ValueError, match="base SQLite de piezas"):
        abrir_catalogo(tmp_path)
