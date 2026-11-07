"""Generate a wholly fictional appliance-parts catalog for demos and tests."""
import argparse
import json
import os
import random
import sqlite3
import tempfile
from datetime import date
from pathlib import Path


AS_OF = date(2026, 11, 7)
CATEGORIES = [
    ("neveras", "Neveras", "compresor termostato evaporador condensador placa sensor puerta sello ventilador filtro"),
    ("congeladores", "Congeladores", "compresor termostato evaporador condensador placa sensor bisagra sello ventilador filtro"),
    ("freezers", "Freezers", "compresor termostato evaporador condensador placa sensor puerta sello ventilador cajon"),
    ("secadoras", "Secadoras de ropa", "motor correa tambor resistencia termostato filtro polea sensor placa puerta"),
    ("fogoes", "Fogões", "quemador valvula termopar perilla rejilla encendedor horno placa bisagra sello"),
    ("hornos", "Hornos", "resistencia termostato ventilador bisagra puerta sello bandeja sensor placa perilla"),
    ("cooktops", "Cooktops", "quemador valvula encendedor perilla vidrio placa sensor bobina cable rejilla"),
    ("lavaloucas", "Lavalouças", "bomba filtro brazo aspersor motor valvula manguera sensor placa sello"),
    ("microondas", "Forno micro-ondas", "magnetron transformador plato motor puerta fusible placa sensor diodo capacitor"),
    ("ar_condicionados", "Ar condicionados", "compresor evaporador condensador ventilador filtro sensor placa control valvula tubo"),
    ("lavadoras", "Máquinas de lavar", "motor bomba tambor correa valvula manguera sensor placa sello filtro"),
]
SUPPLIERS = [
    ("BR-01", "Brava Peças", "BR", "BRL"),
    ("BR-02", "Sul Componentes", "BR", "BRL"),
    ("BR-03", "Norte Reposição", "BR", "BRL"),
    ("BR-04", "Casa Técnica Brasil", "BR", "BRL"),
    ("BR-05", "Litoral Parts", "BR", "BRL"),
    ("BR-06", "CentroPeças", "BR", "BRL"),
    ("INT-01", "North Parts Trading", "US", "USD"),
    ("INT-02", "EuroSpare Components", "DE", "EUR"),
    ("INT-03", "TecnoParts Italia", "IT", "EUR"),
    ("INT-04", "Pacific Appliance Supply", "CN", "USD"),
    ("INT-05", "Global Fix México", "MX", "USD"),
    ("INT-06", "Atlantic Repair Parts", "US", "USD"),
]
FAKE_BRL_RATE = {"BRL": 1, "USD": 5, "EUR": 6}
BRANDS = ["Aurora", "Brisa", "Domus", "Estrela", "Horizonte", "VivaCasa", "NovaLar", "Solare"]
MATERIALS = ["aço", "alumínio", "cobre", "plástico ABS", "borracha", "cerâmica"]

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL);
CREATE TABLE suppliers (
  id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, country_code TEXT NOT NULL,
  domestic INTEGER NOT NULL CHECK(domestic IN (0,1)), currency TEXT NOT NULL,
  website TEXT NOT NULL);
CREATE TABLE parts (
  id TEXT PRIMARY KEY, sku TEXT UNIQUE NOT NULL, category_id INTEGER NOT NULL,
  family TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL,
  manufacturer TEXT NOT NULL, part_kind TEXT NOT NULL, material TEXT NOT NULL,
  color TEXT NOT NULL, voltage_v INTEGER, power_w INTEGER,
  length_mm INTEGER NOT NULL, width_mm INTEGER NOT NULL, height_mm INTEGER NOT NULL,
  weight_g INTEGER NOT NULL, warranty_months INTEGER NOT NULL,
  origin_country TEXT NOT NULL, condition TEXT NOT NULL,
  technical_specs_json TEXT NOT NULL, image_url TEXT,
  FOREIGN KEY(category_id) REFERENCES categories(id));
CREATE TABLE compatibility (
  part_id TEXT NOT NULL, brand TEXT NOT NULL, model_code TEXT NOT NULL,
  year_from INTEGER NOT NULL, year_to INTEGER NOT NULL,
  PRIMARY KEY(part_id, brand, model_code), FOREIGN KEY(part_id) REFERENCES parts(id));
CREATE TABLE offers (
  id TEXT PRIMARY KEY, part_id TEXT NOT NULL, supplier_id TEXT NOT NULL,
  currency TEXT NOT NULL, unit_price_minor INTEGER NOT NULL CHECK(unit_price_minor>0),
  estimated_brl_cents INTEGER NOT NULL CHECK(estimated_brl_cents>0),
  stock_qty INTEGER NOT NULL CHECK(stock_qty>=0),
  availability TEXT NOT NULL CHECK(availability IN ('in_stock','backorder','discontinued')),
  restock_date TEXT, shipping_brl_cents INTEGER NOT NULL CHECK(shipping_brl_cents>=0),
  lead_days INTEGER NOT NULL CHECK(lead_days>=0), min_order_qty INTEGER NOT NULL,
  updated_on TEXT NOT NULL, FOREIGN KEY(part_id) REFERENCES parts(id),
  FOREIGN KEY(supplier_id) REFERENCES suppliers(id));
CREATE TABLE price_history (
  offer_id TEXT NOT NULL, observed_on TEXT NOT NULL,
  unit_price_minor INTEGER NOT NULL, estimated_brl_cents INTEGER NOT NULL,
  PRIMARY KEY(offer_id, observed_on), FOREIGN KEY(offer_id) REFERENCES offers(id));
CREATE INDEX idx_parts_category ON parts(category_id, family);
CREATE INDEX idx_parts_name ON parts(name);
CREATE INDEX idx_offers_part ON offers(part_id, availability, estimated_brl_cents);
CREATE INDEX idx_offers_supplier ON offers(supplier_id);
CREATE INDEX idx_compatibility_model ON compatibility(brand, model_code);
"""


def generate(output: Path, *, pieces_per_category: int = 240, seed: int = 20261107) -> dict[str, int]:
    if pieces_per_category < 1:
        raise ValueError("pieces_per_category must be positive")
    rng = random.Random(seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".piezas-", suffix=".sqlite3", dir=output.parent)
    os.close(fd)
    counts = {"categories": len(CATEGORIES), "parts": 0, "offers": 0, "compatibility": 0,
              "price_history": 0}
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript(SCHEMA)
            db.executemany("INSERT INTO metadata VALUES (?,?)", [
                ("source", "100% synthetic; no real inventory, prices, suppliers or compatibility"),
                ("generator", "scripts/generar_catalogo_piezas.py"),
                ("seed", str(seed)), ("as_of", AS_OF.isoformat()),
                ("price_note", "All BRL conversions and shipping charges are fictional estimates"),
            ])
            db.executemany("INSERT INTO categories VALUES (?,?,?)",
                           [(i, slug, name) for i, (slug, name, _) in enumerate(CATEGORIES, 1)])
            db.executemany("INSERT INTO suppliers VALUES (?,?,?,?,?,?)", [
                (sid, name, country, int(country == "BR"), currency,
                 f"https://{sid.lower()}.example") for sid, name, country, currency in SUPPLIERS])
            domestic = [s for s in SUPPLIERS if s[2] == "BR"]
            international = [s for s in SUPPLIERS if s[2] != "BR"]
            for category_id, (slug, category_name, families) in enumerate(CATEGORIES, 1):
                choices = families.split()
                for number in range(1, pieces_per_category + 1):
                    part_id = f"PEC-{category_id:02d}-{number:04d}"
                    family = choices[(number - 1) % len(choices)]
                    sku = f"{slug[:4].upper()}-{family[:4].upper()}-{number:04d}"
                    voltage = rng.choice([110, 127, 220, 240]) if family in {
                        "compresor", "motor", "resistencia", "placa", "ventilador", "bomba", "magnetron"} else None
                    power = rng.randrange(80, 2600, 20) if voltage is not None else None
                    specs = {"connector": rng.choice(["2 pinos", "3 pinos", "terminal", "sem conector"]),
                             "installation": "técnico qualificado", "packaging": "caixa individual",
                             "series": f"S{rng.randint(1, 9)}"}
                    db.execute("INSERT INTO parts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                        part_id, sku, category_id, family, f"{family.title()} para {category_name} {sku}",
                        f"Peça fictícia de reposição para {category_name.lower()}; confira o modelo compatível.",
                        rng.choice(BRANDS) + " Components", rng.choice(["OEM", "compatível", "remanufaturada"]),
                        rng.choice(MATERIALS), rng.choice(["preto", "branco", "prata", "natural"]),
                        voltage, power, rng.randint(25, 480), rng.randint(20, 360), rng.randint(5, 210),
                        rng.randint(40, 9500), rng.choice([3, 6, 12, 18, 24]),
                        rng.choice(["BR", "CN", "US", "DE", "IT", "MX"]), "nova",
                        json.dumps(specs, ensure_ascii=False), None))
                    counts["parts"] += 1
                    for brand in rng.sample(BRANDS, 3):
                        year_from = rng.randint(2015, 2023)
                        db.execute("INSERT INTO compatibility VALUES (?,?,?,?,?)", (
                            part_id, brand, f"{slug[:3].upper()}-{rng.randint(1000, 9999)}",
                            year_from, rng.randint(year_from, 2026)))
                        counts["compatibility"] += 1
                    suppliers = rng.sample(domestic, 2) + rng.sample(international, 1)
                    for supplier in suppliers:
                        supplier_id, _, country, currency = supplier
                        offer_id = f"{part_id}-{supplier_id}"
                        base_brl = rng.randint(2500, 145000)
                        price_minor = max(100, base_brl // FAKE_BRL_RATE[currency])
                        history = []
                        for month in range(6, 12):
                            month_price = max(100, price_minor * rng.randint(85, 115) // 100)
                            history.append((offer_id, date(2026, month, 7).isoformat(), month_price,
                                            month_price * FAKE_BRL_RATE[currency]))
                        current = history[-1]
                        availability = rng.choices(
                            ["in_stock", "backorder", "discontinued"], weights=[72, 20, 8])[0]
                        stock = rng.randint(1, 120) if availability == "in_stock" else 0
                        lead_days = rng.randint(2, 12) if country == "BR" else rng.randint(16, 45)
                        restock = (date(2026, 12, rng.randint(1, 25)).isoformat()
                                   if availability == "backorder" else None)
                        shipping = rng.randint(1200, 12000) if country == "BR" else rng.randint(12000, 55000)
                        db.execute("INSERT INTO offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                            offer_id, part_id, supplier_id, currency, current[2], current[3], stock,
                            availability, restock, shipping, lead_days, rng.choice([1, 1, 1, 2, 5]),
                            AS_OF.isoformat()))
                        db.executemany("INSERT INTO price_history VALUES (?,?,?,?)", history)
                        counts["offers"] += 1
                        counts["price_history"] += len(history)
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("foreign key check failed")
        os.replace(temporary, output)
        output.chmod(0o644)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("datasets/piezas_electrodomesticos.sqlite3"))
    parser.add_argument("--pieces-per-category", type=int, default=240)
    parser.add_argument("--seed", type=int, default=20261107)
    args = parser.parse_args()
    print(json.dumps(generate(args.output, pieces_per_category=args.pieces_per_category,
                              seed=args.seed), indent=2))
