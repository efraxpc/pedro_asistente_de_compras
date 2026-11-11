"""Escenarios inmutables a partir de una base sintética reproducible."""
import hashlib
import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .contracts import Oferta

SOURCE = Path(__file__).resolve().parents[2] / "datasets/piezas_electrodomesticos.sqlite3"


@dataclass(frozen=True)
class Escenario:
    dataset_id: str
    ruta: Path


def conectar(escenario: Escenario) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{escenario.ruta}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def crear_escenario(base: Path, source: Path = SOURCE) -> Escenario:
    if not source.is_file():
        raise FileNotFoundError(source)
    identificador = str(uuid.uuid4())
    carpeta = base / identificador
    carpeta.mkdir(parents=True, exist_ok=False)
    destino = carpeta / "catalogo.sqlite3"
    shutil.copyfile(source, destino)
    huella = hashlib.sha256(destino.read_bytes()).hexdigest()
    escenario = Escenario(identificador, destino)
    with conectar(escenario) as db:
        recuentos = {tabla: db.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]
                    for tabla in ("parts", "offers", "compatibility", "price_history")}
        semilla = db.execute("SELECT value FROM metadata WHERE key='seed'").fetchone()[0]
    manifiesto = {"dataset_id": identificador, "version": "synthetic-parts-v1",
                  "capturado_en": datetime.now(timezone.utc).isoformat(),
                  "fuente": str(source.resolve()), "semilla": int(semilla),
                  "sha256": huella, "recuentos": recuentos}
    (carpeta / "manifest.json").write_text(json.dumps(manifiesto, indent=2), encoding="utf-8")
    return escenario


def abrir_escenario(base: Path, dataset_id: str) -> Escenario:
    uuid.UUID(dataset_id)
    carpeta = base / dataset_id
    meta = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
    ruta = carpeta / "catalogo.sqlite3"
    if meta["dataset_id"] != dataset_id or hashlib.sha256(ruta.read_bytes()).hexdigest() != meta["sha256"]:
        raise ValueError("manifesto o catálogo alterado")
    return Escenario(dataset_id, ruta)


def buscar(escenario: Escenario, texto: str, limite: int = 20) -> list[dict]:
    if not texto.strip():
        return []
    patron = f"%{texto.strip().lower()}%"
    with conectar(escenario) as db:
        filas = db.execute("SELECT p.id,p.sku,p.name,c.name AS category FROM parts p "
                           "JOIN categories c ON c.id=p.category_id WHERE lower(p.id)=? "
                           "OR lower(p.sku)=? OR lower(p.name) LIKE ? ORDER BY p.id LIMIT ?",
                           (texto.lower(), texto.lower(), patron, min(max(limite, 1), 50))).fetchall()
    return [dict(f) for f in filas]


def listar(escenario: Escenario, pagina: int = 1, termino: str = "") -> tuple[int, list[dict]]:
    if pagina < 1:
        raise ValueError("página inválida")
    patron = f"%{termino.strip().lower()}%"
    filtro = "WHERE lower(p.name) LIKE ? OR lower(p.sku) LIKE ? OR lower(p.id) LIKE ?"
    with conectar(escenario) as db:
        total = db.execute(f"SELECT count(*) FROM parts p {filtro}", (patron,) * 3).fetchone()[0]
        filas = db.execute(f"SELECT p.id,p.sku,p.name,c.name AS category FROM parts p "
                           f"JOIN categories c ON c.id=p.category_id {filtro} "
                           "ORDER BY p.id LIMIT 20 OFFSET ?", (*((patron,) * 3), (pagina - 1) * 20)).fetchall()
    return total, [dict(f) for f in filas]


def ficha(escenario: Escenario, producto_id: str) -> dict | None:
    with conectar(escenario) as db:
        fila = db.execute("SELECT p.*,c.name AS category FROM parts p JOIN categories c "
                          "ON c.id=p.category_id WHERE p.id=?", (producto_id,)).fetchone()
        if fila is None:
            return None
        dato = dict(fila)
        dato["compatibility"] = [dict(f) for f in db.execute(
            "SELECT brand,model_code,year_from,year_to FROM compatibility WHERE part_id=?", (producto_id,))]
    return dato


def ofertas(escenario: Escenario, producto_id: str) -> list[Oferta]:
    with conectar(escenario) as db:
        filas = db.execute("SELECT o.id,o.part_id AS producto_id,o.supplier_id AS proveedor_id,"
                           "s.name AS proveedor_nombre,o.estimated_brl_cents AS precio_unitario_centavos,"
                           "o.shipping_brl_cents AS flete_centavos,o.stock_qty AS stock,"
                           "o.lead_days AS plazo_dias,o.min_order_qty AS pedido_minimo,"
                           "s.domestic AS nacional FROM offers o JOIN suppliers s ON s.id=o.supplier_id "
                           "WHERE o.part_id=? ORDER BY o.supplier_id", (producto_id,)).fetchall()
    return [Oferta(dataset_id=escenario.dataset_id, **dict(f)) for f in filas]
