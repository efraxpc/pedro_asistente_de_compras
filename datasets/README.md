# Catálogo ficticio de piezas

`piezas_electrodomesticos.sqlite3` es una base SQLite reproducible de **2.640 piezas**, **7.920 ofertas** y **47.520 registros de precios históricos**. Incluye 240 piezas para cada una de las 11 familias solicitadas: neveras, congeladores, freezers, secadoras de ropa, fogões, hornos, cooktops, lavalouças, forno micro-ondas, ar condicionados y máquinas de lavar.

Todos los nombres de proveedores, compatibilidades, existencias, precios y conversiones a BRL son **ficticios**. No utilice esta base para comprar piezas reales ni suponga que un modelo indicado es compatible con un aparato físico.

La app usa esta base como única fuente de productos. Al pulsar «Nuevo escenario», copia las 2.640 piezas y sus ofertas a una instantánea independiente en `storage/catalogos/`; los IDs del chat son `PROD-####`, mientras que el SKU original de la pieza permanece en el campo `modelo`. Los chats antiguos de otras fuentes conservan su historial, pero no reabren sus catálogos. La vista «Catálogo de piezas» lee los detalles de esta base SQLite y limita los resultados a los SKU del escenario activo; permite buscar y filtrar las piezas y consultar compatibilidades, ofertas e historial. El chat ofrece listados paginados y fichas por ID o SKU.

## Tablas

- `categories`: familias de electrodomésticos.
- `parts`: SKU, tipo de pieza, nombre, descripción, fabricante ficticio, material, color, voltaje, potencia, dimensiones, peso, garantía, origen y especificaciones adicionales JSON.
- `compatibility`: marcas/modelos ficticios y rango de años para cada pieza.
- `suppliers`: seis proveedores nacionales y seis internacionales, con país, moneda y URL `.example`.
- `offers`: precio en moneda del proveedor y estimación ficticia en centavos de BRL, stock, disponibilidad, reposición, flete, plazo y pedido mínimo.
- `price_history`: seis valores mensuales por oferta; el último coincide con el precio vigente en `offers`.
- `metadata`: procedencia, semilla, fecha de la instantánea y advertencias.

## Regenerar y consultar

```bash
uv run python scripts/generar_catalogo_piezas.py
sqlite3 datasets/piezas_electrodomesticos.sqlite3 \
  "SELECT c.name, count(*) FROM parts p JOIN categories c ON c.id=p.category_id GROUP BY c.id;"
sqlite3 datasets/piezas_electrodomesticos.sqlite3 \
  "SELECT p.sku, p.name, s.name, o.estimated_brl_cents, o.stock_qty FROM offers o JOIN parts p ON p.id=o.part_id JOIN suppliers s ON s.id=o.supplier_id LIMIT 10;"
```

El generador acepta `--pieces-per-category`, `--seed` y `--output`. Los importes se almacenan en unidades menores enteras para evitar errores de punto flotante.
