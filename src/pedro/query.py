"""Text-to-query: el modelo compila un plan, nunca SQL libre."""
import re
from typing import Literal

from pydantic import BaseModel, Field

from .catalog import Escenario, conectar


class PlanConsulta(BaseModel):
    objetivo: Literal["pieza", "ofertas"]
    producto_id: str = Field(pattern=r"^PEC-[0-9]{2}-[0-9]{4}$")
    limite: int = Field(default=20, ge=1, le=50)


SQL = {
    "pieza": "SELECT id,sku,name,description FROM parts WHERE id=? LIMIT ?",
    "ofertas": "SELECT o.id,o.part_id,o.supplier_id,s.name AS proveedor,"
               "o.estimated_brl_cents,o.shipping_brl_cents,o.stock_qty,o.lead_days "
               "FROM offers o JOIN suppliers s ON s.id=o.supplier_id "
               "WHERE o.part_id=? ORDER BY o.supplier_id LIMIT ?",
}


def planear(pregunta: str) -> PlanConsulta:
    ids = set(re.findall(r"\bPEC-[0-9]{2}-[0-9]{4}\b", pregunta.upper()))
    if len(ids) != 1:
        raise ValueError("se requiere un único ID de pieza")
    objetivo = "ofertas" if re.search(r"oferta|precio|stock|proveedor|plazo", pregunta, re.I) else "pieza"
    return PlanConsulta(objetivo=objetivo, producto_id=ids.pop())


def ejecutar(escenario: Escenario, pregunta: str, plan: PlanConsulta) -> dict:
    sql = SQL[plan.objetivo]
    parametros = [plan.producto_id, plan.limite]
    with conectar(escenario) as db:
        filas = [dict(f) for f in db.execute(sql, parametros)]
    return {"pregunta": pregunta, "plan": plan.model_dump(), "sql": sql,
            "parametros": parametros, "filas": filas, "dataset_id": escenario.dataset_id}
