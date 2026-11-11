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


# --- Text-to-SQL con modelo: el LLM escribe el SELECT y el motor decide si lo ejecuta. ---

# Tablas y columnas que una consulta generada puede leer. Lo que no está aquí no existe.
ESQUEMA_PERMITIDO: dict[str, tuple[str, ...]] = {
    "parts": ("id", "sku", "category_id", "family", "name", "description", "manufacturer",
              "part_kind", "material", "color", "voltage_v", "power_w", "weight_g",
              "warranty_months", "origin_country", "condition"),
    "categories": ("id", "slug", "name"),
    "suppliers": ("id", "name", "country_code", "domestic", "currency"),
    "offers": ("id", "part_id", "supplier_id", "estimated_brl_cents", "shipping_brl_cents",
               "stock_qty", "availability", "lead_days", "min_order_qty"),
    "compatibility": ("part_id", "brand", "model_code", "year_from", "year_to"),
}
FUNCIONES_PERMITIDAS = {"count", "sum", "avg", "min", "max", "round", "lower", "upper", "length",
                        "substr", "coalesce", "abs", "like", "total"}
MAX_FILAS = 50
MAX_PASOS = 2_000_000


class ConsultaSQL(BaseModel):
    """Lo que debe devolver el modelo: una sola consulta de lectura y su explicación."""
    sql: str = Field(description="Un único SELECT de SQLite, sin punto y coma final")
    explicacion: str = Field(description="Una frase: qué responde la consulta")


class ConsultaRechazada(ValueError):
    """La consulta generada no pasó la validación o el motor no la autorizó."""


def describir_esquema() -> str:
    return "\n".join(f"- {tabla}({', '.join(columnas)})"
                     for tabla, columnas in ESQUEMA_PERMITIDO.items())


def validar_sql(sql: str) -> str:
    """Comprobación de forma antes de tocar la base: una sola sentencia y que sea SELECT."""
    limpio = sql.strip().rstrip(";").strip()
    if not limpio:
        raise ConsultaRechazada("consulta vacía")
    if ";" in limpio:
        raise ConsultaRechazada("solo se admite una sentencia")
    if not re.match(r"(?is)^select\b", limpio):
        raise ConsultaRechazada("solo se admiten consultas SELECT")
    if re.search(r"--|/\*", limpio):
        raise ConsultaRechazada("no se admiten comentarios")
    return limpio


def consultar_sql(escenario: Escenario, sql: str) -> dict:
    """Valida y ejecuta un SELECT generado, con el motor como árbitro.

    Tres barreras: la forma (una sentencia SELECT), el autorizador de SQLite (solo las tablas,
    columnas y funciones permitidas; cualquier otra acción se deniega) y los límites (base en
    solo lectura, 50 filas como máximo y tope de pasos de ejecución).
    """
    import sqlite3

    limpio = validar_sql(sql)
    denegado: list[str] = []

    def autorizar(accion, arg1, arg2, _base, _origen):
        if accion == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if accion == sqlite3.SQLITE_READ:
            if arg1 in ESQUEMA_PERMITIDO and (not arg2 or arg2 in ESQUEMA_PERMITIDO[arg1]):
                return sqlite3.SQLITE_OK
            denegado.append(f"lectura de {arg1}.{arg2 or '*'}")
            return sqlite3.SQLITE_DENY
        if accion == sqlite3.SQLITE_FUNCTION and str(arg2).lower() in FUNCIONES_PERMITIDAS:
            return sqlite3.SQLITE_OK
        denegado.append(f"acción {accion} sobre {arg1 or arg2}")
        return sqlite3.SQLITE_DENY

    pasos = [0]

    def vigilar() -> int:
        pasos[0] += 10_000
        return 1 if pasos[0] > MAX_PASOS else 0

    with conectar(escenario) as db:
        db.set_authorizer(autorizar)
        db.set_progress_handler(vigilar, 10_000)
        try:
            cursor = db.execute(limpio)
            filas = [dict(f) for f in cursor.fetchmany(MAX_FILAS + 1)]
        except sqlite3.Error as exc:
            motivo = "; ".join(denegado) or str(exc)
            raise ConsultaRechazada(f"el motor no autorizó la consulta: {motivo}") from exc
        finally:
            db.set_authorizer(None)
            db.set_progress_handler(None, 0)
    return {"sql": limpio, "filas": filas[:MAX_FILAS], "truncado": len(filas) > MAX_FILAS,
            "dataset_id": escenario.dataset_id}


def crear_generador_sql(modelo):
    """Cadena que convierte una pregunta en una `ConsultaSQL`. No ejecuta nada."""
    from langchain_core.output_parsers import PydanticOutputParser

    from .prompts import PLANTILLA_SQL

    parser = PydanticOutputParser(pydantic_object=ConsultaSQL)
    return (PLANTILLA_SQL.partial(esquema=describir_esquema(), max_filas=str(MAX_FILAS),
                                  formato=parser.get_format_instructions()) | modelo | parser)


def responder_sql(escenario: Escenario, pregunta: str, generador) -> dict:
    """Text-to-SQL completo: generar, validar, ejecutar y, si falla, corregir una vez."""
    intentos = []
    error = ""
    for _ in range(2):
        try:
            consulta: ConsultaSQL = generador.invoke({"pregunta": pregunta, "error": error})
        except Exception as exc:  # salida ilegible del modelo
            intentos.append({"sql": None, "error": type(exc).__name__})
            error = "La respuesta anterior no era el JSON pedido."
            continue
        try:
            resultado = consultar_sql(escenario, consulta.sql)
        except ConsultaRechazada as exc:
            intentos.append({"sql": consulta.sql, "error": str(exc)})
            error = f"La consulta anterior fue rechazada: {exc}. Consulta rechazada: {consulta.sql}"
            continue
        intentos.append({"sql": resultado["sql"], "error": None})
        # Una consulta válida puede estar mal planteada: cero filas se señala, no se da por bueno.
        estado = "ok" if resultado["filas"] else "sin_filas"
        return {"pregunta": pregunta, "estado": estado, "explicacion": consulta.explicacion,
                "intentos": intentos, **resultado}
    return {"pregunta": pregunta, "estado": "rechazada", "intentos": intentos, "filas": [],
            "dataset_id": escenario.dataset_id}
