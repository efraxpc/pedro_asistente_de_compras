"""Read the complete fictional parts catalog for the active SQLite scenario."""
import json
import sqlite3

from .data import Catalogo, PIEZAS_DB, conectar


def _active_products(catalogo: Catalogo) -> dict[str, str]:
    if catalogo.modo != "piezas":
        raise ValueError("el escenario activo no usa piezas")
    with conectar(catalogo.ruta) as db:
        return {row["modelo"]: row["id"] for row in db.execute(
            "SELECT id, modelo FROM producto WHERE dataset_id=?", (catalogo.dataset_id,))}


def listar_piezas(catalogo: Catalogo) -> list[dict]:
    """Return every part in the active scenario, with source category and offer totals."""
    active = _active_products(catalogo)
    if not PIEZAS_DB.is_file():
        raise FileNotFoundError(PIEZAS_DB)
    with conectar(PIEZAS_DB) as db:
        rows = db.execute("""
            SELECT p.sku, p.name, c.name AS category, p.part_kind, p.manufacturer,
                   MIN(o.estimated_brl_cents) AS min_price_brl_cents,
                   SUM(o.stock_qty) AS total_stock, COUNT(o.id) AS offer_count
            FROM parts p JOIN categories c ON c.id=p.category_id
            LEFT JOIN offers o ON o.part_id=p.id
            GROUP BY p.id ORDER BY c.name, p.name, p.sku
        """).fetchall()
    return [{"product_id": active[row["sku"]], **dict(row)}
            for row in rows if row["sku"] in active]


def detalle_pieza(catalogo: Catalogo, sku: str) -> dict | None:
    """Return all source fields, compatibilities, offers and price history for one SKU."""
    active = _active_products(catalogo)
    if sku not in active:
        return None
    if not PIEZAS_DB.is_file():
        raise FileNotFoundError(PIEZAS_DB)
    with conectar(PIEZAS_DB) as db:
        part = db.execute("""
            SELECT p.*, c.name AS category, c.slug AS category_slug
            FROM parts p JOIN categories c ON c.id=p.category_id WHERE p.sku=?
        """, (sku,)).fetchone()
        if part is None:
            return None
        compatibility = [dict(row) for row in db.execute(
            "SELECT brand, model_code, year_from, year_to FROM compatibility "
            "WHERE part_id=? ORDER BY brand, model_code", (part["id"],))]
        offers = [dict(row) for row in db.execute("""
            SELECT o.*, s.name AS supplier_name, s.country_code, s.domestic,
                   s.website FROM offers o JOIN suppliers s ON s.id=o.supplier_id
            WHERE o.part_id=? ORDER BY o.estimated_brl_cents, o.id
        """, (part["id"],))]
        histories = {offer["id"]: [dict(row) for row in db.execute(
            "SELECT observed_on, unit_price_minor, estimated_brl_cents "
            "FROM price_history WHERE offer_id=? ORDER BY observed_on", (offer["id"],))]
            for offer in offers}
    result = dict(part)
    result["product_id"] = active[sku]
    result["technical_specs"] = json.loads(result.pop("technical_specs_json"))
    result["compatibility"] = compatibility
    result["offers"] = offers
    result["price_history"] = histories
    return result
