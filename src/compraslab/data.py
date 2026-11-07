"""Instantáneas ficticias en SQLite; una conexión activa nunca cambia de dataset."""
import json
import random
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .schemas import Oferta, Producto

GENERATOR_VERSION = "1"
PROVEEDORES = (("DEMO-A", "Demo A"), ("DEMO-B", "Demo B"), ("DEMO-C", "Demo C"))


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


def crear_catalogo(base: Path, *, modo: str = "random", cantidad: int = 1000,
                   semilla: int | None = None) -> Catalogo:
    if modo != "random":
        raise ValueError("modo referencia requiere el kit original")
    if cantidad < 1:
        raise ValueError("cantidad debe ser positiva")
    semilla = secrets.randbelow(2**63) if semilla is None else semilla
    if not 0 <= semilla < 2**63:
        raise ValueError("semilla fuera de rango")
    dataset_id = str(uuid.uuid4())
    carpeta = base / dataset_id
    carpeta.mkdir(parents=True, exist_ok=False)
    ruta = carpeta / "catalogo.sqlite3"
    rng = random.Random(semilla)
    with conectar(ruta) as db:
        crear_esquema(db)
        db.execute("INSERT INTO dataset VALUES (?,?,?,?)", (dataset_id, modo, semilla, GENERATOR_VERSION))
        db.executemany("INSERT INTO proveedor VALUES (?,?,?)",
                       [(dataset_id, id_, nombre) for id_, nombre in PROVEEDORES])
        for n in range(1, cantidad + 1):
            pid = f"PROD-{n:03d}"
            nombre = "Monitor" if n % 17 == 3 else ("Notebook" if n % 2 else "Teclado")
            db.execute("INSERT INTO producto VALUES (?,?,?,?,?)",
                       (dataset_id, pid, nombre, f"Modelo {n:04d}", "unidade"))
            for proveedor_id, _ in PROVEEDORES:
                db.execute("INSERT INTO oferta VALUES (?,?,?,?,?,?,?,?)",
                           (dataset_id, f"{pid}-{proveedor_id}", pid, proveedor_id,
                            rng.randint(10000, 120000), rng.randint(0, 30000),
                            rng.randint(0, 100), rng.randint(1, 20)))
    (carpeta / "manifest.json").write_text(json.dumps({
        "dataset_id": dataset_id, "modo": modo, "semilla": semilla,
        "cantidad_productos": cantidad, "generador": GENERATOR_VERSION,
        "sqlite": str(ruta)}, indent=2), encoding="utf-8")
    return Catalogo(dataset_id, ruta, semilla, modo)


def abrir_catalogo(carpeta: Path) -> Catalogo:
    meta = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
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


def ofertas_producto(catalogo: Catalogo, producto_id: str) -> list[Oferta]:
    with conectar(catalogo.ruta) as db:
        filas = db.execute("SELECT o.*, p.nombre AS proveedor_nombre FROM oferta o JOIN proveedor p "
                           "ON p.dataset_id=o.dataset_id AND p.id=o.proveedor_id "
                           "WHERE o.dataset_id=? AND o.producto_id=? ORDER BY o.proveedor_id",
                           (catalogo.dataset_id, producto_id)).fetchall()
    return [Oferta(**dict(f)) for f in filas]
