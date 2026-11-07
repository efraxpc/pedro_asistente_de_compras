"""Text-to-query acotado: genera un plan tipado y SQL fijo de solo lectura.

El modelo puede elegir el objetivo y filtros del plan; nunca entrega SQL ejecutable.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

from .data import Catalogo, conectar
from .schemas import Evidencia, ResultadoHerramienta


class PlanConsulta(BaseModel):
    objetivo: Literal["producto", "ofertas"]
    producto_id: str = Field(pattern=r"^PROD-[0-9]{3,}$")
    limite: int = Field(default=10, ge=1, le=50)


SQL = {
    "producto": "SELECT id,nombre,modelo,unidad FROM producto WHERE dataset_id=? AND id=? LIMIT ?",
    "ofertas": "SELECT o.id,o.producto_id,o.proveedor_id,p.nombre AS proveedor_nombre,"
               "o.precio_unitario_centavos,o.flete_centavos,o.stock,o.plazo_dias "
               "FROM oferta o JOIN proveedor p ON p.dataset_id=o.dataset_id AND p.id=o.proveedor_id "
               "WHERE o.dataset_id=? AND o.producto_id=? ORDER BY o.proveedor_id LIMIT ?",
}


def plan_desde_pregunta(pregunta: str) -> PlanConsulta:
    """Ruta offline didáctica; el modelo puede producir el mismo PlanConsulta."""
    ids = re.findall(r"\bPROD-[0-9]{3,}\b", pregunta.upper())
    if len(set(ids)) != 1:
        raise ValueError("la pregunta debe identificar un único producto")
    objetivo = "ofertas" if re.search(r"oferta|precio|proveedor|stock|plazo", pregunta, re.I) else "producto"
    return PlanConsulta(objetivo=objetivo, producto_id=ids[0])


def ejecutar_plan(catalogo: Catalogo, plan: PlanConsulta) -> ResultadoHerramienta:
    sql = SQL[plan.objetivo]
    parametros = (catalogo.dataset_id, plan.producto_id, plan.limite)
    with conectar(catalogo.ruta) as db:
        filas = [dict(f) for f in db.execute(sql, parametros).fetchall()]
    evidencias = [Evidencia(tipo="catalogo", fuente_id=f["id"], dataset_id=catalogo.dataset_id,
                           texto=(f"{f.get('proveedor_nombre', f.get('nombre', ''))}: "
                                  f"{f}")) for f in filas]
    return ResultadoHerramienta(nombre="consultar_catalogo", estado="ok" if filas else "no_encontrado",
        datos={"sql": sql, "parametros": list(parametros), "validacion": "plantilla permitida",
               "filas": filas}, evidencias=evidencias)


def text_to_query(catalogo: Catalogo, pregunta: str) -> ResultadoHerramienta:
    try:
        return ejecutar_plan(catalogo, plan_desde_pregunta(pregunta))
    except ValueError as exc:
        return ResultadoHerramienta(nombre="consultar_catalogo", estado="invalido", error=str(exc))
