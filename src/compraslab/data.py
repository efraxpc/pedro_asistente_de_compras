"""Instantáneas ficticias en SQLite; una conexión activa nunca cambia de dataset."""
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .schemas import Oferta, Producto

PIEZAS_DB = Path(__file__).resolve().parents[2] / "datasets/piezas_electrodomesticos.sqlite3"


@dataclass(frozen=True)
class Catalogo:
    dataset_id: str
    ruta: Path
    semilla: int | None
    modo: str


def conectar(ruta: Path) -> sqlite3.Connection:
    db = sqlite3.connect(ruta)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def crear_esquema(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS dataset (id TEXT PRIMARY KEY, modo TEXT NOT NULL,
      semilla INTEGER, generador TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS producto (dataset_id TEXT NOT NULL, id TEXT NOT NULL,
      nombre TEXT NOT NULL, modelo TEXT NOT NULL, unidad TEXT NOT NULL,
      PRIMARY KEY(dataset_id,id), FOREIGN KEY(dataset_id) REFERENCES dataset(id));
    CREATE TABLE IF NOT EXISTS proveedor (dataset_id TEXT NOT NULL, id TEXT NOT NULL,
      nombre TEXT NOT NULL, PRIMARY KEY(dataset_id,id), FOREIGN KEY(dataset_id) REFERENCES dataset(id));
    CREATE TABLE IF NOT EXISTS oferta (dataset_id TEXT NOT NULL, id TEXT NOT NULL,
      producto_id TEXT NOT NULL, proveedor_id TEXT NOT NULL,
      precio_unitario_centavos INTEGER NOT NULL CHECK(precio_unitario_centavos>=0),
      flete_centavos INTEGER NOT NULL CHECK(flete_centavos>=0),
      stock INTEGER NOT NULL CHECK(stock>=0), plazo_dias INTEGER NOT NULL CHECK(plazo_dias>=0),
      PRIMARY KEY(dataset_id,id), FOREIGN KEY(dataset_id,producto_id) REFERENCES producto(dataset_id,id),
      FOREIGN KEY(dataset_id,proveedor_id) REFERENCES proveedor(dataset_id,id));
    CREATE INDEX IF NOT EXISTS idx_producto_nombre ON producto(dataset_id,nombre);
    CREATE INDEX IF NOT EXISTS idx_oferta_produto ON oferta(dataset_id,producto_id);
    """)


def crear_catalogo(base: Path, *, cantidad: int = 3000) -> Catalogo:
    """Create a scenario exclusively from the local appliance-parts SQLite database."""
    return crear_catalogo_piezas(base, cantidad=cantidad)


def crear_catalogo_piezas(base: Path, *, cantidad: int = 3000) -> Catalogo:
    """Copy fictional appliance parts and their offers into an immutable scenario."""
    if cantidad < 1:
        raise ValueError("cantidad debe ser positiva")
    if not PIEZAS_DB.is_file():
        raise FileNotFoundError(PIEZAS_DB)
    with sqlite3.connect(PIEZAS_DB) as origen:
        piezas = origen.execute("SELECT id, sku, name FROM parts ORDER BY id LIMIT ?",
                               (cantidad,)).fetchall()
        proveedores = origen.execute("SELECT id, name FROM suppliers ORDER BY id").fetchall()
        ofertas = origen.execute("SELECT part_id, supplier_id, estimated_brl_cents, "
                                 "shipping_brl_cents, stock_qty, lead_days FROM offers").fetchall()
        fecha = origen.execute("SELECT value FROM metadata WHERE key='as_of'").fetchone()[0]
    if not piezas:
        raise ValueError("catálogo de piezas vacío")
    dataset_id = str(uuid.uuid4())
    carpeta = base / dataset_id
    carpeta.mkdir(parents=True, exist_ok=False)
    ruta = carpeta / "catalogo.sqlite3"
    ids = {part_id: f"PROD-{i:04d}" for i, (part_id, _, _) in enumerate(piezas, 1)}
    with conectar(ruta) as db:
        crear_esquema(db)
        db.execute("INSERT INTO dataset VALUES (?,?,?,?)", (dataset_id, "piezas", None, "parts-v1"))
        db.executemany("INSERT INTO proveedor VALUES (?,?,?)",
                       [(dataset_id, sid, name) for sid, name in proveedores])
        db.executemany("INSERT INTO producto VALUES (?,?,?,?,?)",
                       [(dataset_id, ids[part_id], name, sku, "pieza")
                        for part_id, sku, name in piezas])
        db.executemany("INSERT INTO oferta VALUES (?,?,?,?,?,?,?,?)", [
            (dataset_id, f"{ids[part_id]}-{supplier_id}", ids[part_id], supplier_id,
             price, shipping, stock, lead)
            for part_id, supplier_id, price, shipping, stock, lead in ofertas if part_id in ids])
    (carpeta / "manifest.json").write_text(json.dumps({
        "dataset_id": dataset_id, "modo": "piezas", "semilla": None,
        "cantidad_productos": len(piezas), "generador": "parts-v1",
        "fuente_productos": str(PIEZAS_DB), "capturado_en": fecha,
        "ofertas": "ficticias; conversiones BRL estimadas",
        "sqlite": str(ruta)}, indent=2), encoding="utf-8")
    return Catalogo(dataset_id, ruta, None, "piezas")


def abrir_catalogo(carpeta: Path) -> Catalogo:
    meta = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
    if meta["modo"] != "piezas":
        raise ValueError("el escenario no usa la base SQLite de piezas")
    ruta = carpeta / "catalogo.sqlite3"
    if not ruta.is_file():
        raise FileNotFoundError(ruta)
    return Catalogo(meta["dataset_id"], ruta, meta["semilla"], meta["modo"])


def buscar_productos(catalogo: Catalogo, texto: str, limite: int = 10) -> list[Producto]:
    if not texto.strip():
        raise ValueError("texto vacío")
    with conectar(catalogo.ruta) as db:
        filas = db.execute("SELECT * FROM producto WHERE dataset_id=? AND "
                           "(lower(nombre) LIKE ? OR lower(modelo) LIKE ? OR lower(id)=?) "
                           "ORDER BY id LIMIT ?",
                           (catalogo.dataset_id, f"%{texto.lower()}%", f"%{texto.lower()}%",
                            texto.lower(), min(max(limite, 1), 50))).fetchall()
    return [Producto(**dict(f)) for f in filas]


def listar_productos(catalogo: Catalogo) -> list[Producto]:
    """List the products in the active snapshot for the local comparison picker."""
    with conectar(catalogo.ruta) as db:
        filas = db.execute("SELECT * FROM producto WHERE dataset_id=? ORDER BY id",
                           (catalogo.dataset_id,)).fetchall()
    return [Producto(**dict(f)) for f in filas]


def ofertas_producto(catalogo: Catalogo, producto_id: str) -> list[Oferta]:
    with conectar(catalogo.ruta) as db:
        filas = db.execute("SELECT o.*, p.nombre AS proveedor_nombre FROM oferta o JOIN proveedor p "
                           "ON p.dataset_id=o.dataset_id AND p.id=o.proveedor_id "
                           "WHERE o.dataset_id=? AND o.producto_id=? ORDER BY o.proveedor_id",
                           (catalogo.dataset_id, producto_id)).fetchall()
    return [Oferta(**dict(f)) for f in filas]
