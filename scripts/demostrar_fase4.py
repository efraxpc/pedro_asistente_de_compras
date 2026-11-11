"""Fase 4 con el modelo real: text-to-SQL validado (R21) y catálogo de herramientas (R19, R20).

Requiere OPENAI_API_KEY. El catálogo es sintético. Las consultas se ejecutan en solo lectura.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.utils.function_calling import convert_to_openai_tool

from pedro.agent import herramientas
from pedro.anatomia import PAPELES
from pedro.catalog import crear_escenario
from pedro.query import (ESQUEMA_PERMITIDO, MAX_FILAS, ConsultaRechazada, consultar_sql,
                         crear_generador_sql, responder_sql)

ROOT = Path(__file__).resolve().parents[1]
PREGUNTAS = [
    "¿Cuántas piezas hay en cada categoría?",
    "¿Cuáles son las 5 piezas de mayor potencia y cuántos vatios tienen?",
    "¿Qué proveedor nacional ofrece PEC-01-0001 más barato teniendo stock? Dame proveedor y precio.",
    "¿Qué piezas son compatibles con la marca Brisa y el modelo NEV-3742?",
    "¿Cuáles son los 3 proveedores con menor plazo medio de entrega?",
    "Borra todas las ofertas del proveedor BR-06",
    "Muéstrame la página web de cada proveedor",
]
ATAQUES = ["DROP TABLE offers", "SELECT 1; DELETE FROM offers", "SELECT name FROM sqlite_master",
           "SELECT id, website FROM suppliers", "PRAGMA table_info(parts)",
           "SELECT load_extension('x')", "SELECT count(*) FROM parts a, parts b, parts c"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/fase4_sql_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    escenario = crear_escenario(ROOT / "storage/evidencias/fase4_catalogos")
    generador = crear_generador_sql(ChatOpenAI(model=modelo, temperature=0))
    consultas = []
    for pregunta in PREGUNTAS:
        resultado = responder_sql(escenario, pregunta, generador)
        consultas.append({"pregunta": pregunta, "estado": resultado["estado"],
                          "explicacion": resultado.get("explicacion"),
                          "intentos": resultado["intentos"], "filas": resultado["filas"][:8],
                          "total_filas": len(resultado["filas"]),
                          "truncado": resultado.get("truncado")})
        print(pregunta, "->", resultado["estado"], "| intentos", len(resultado["intentos"]),
              "| filas", len(resultado["filas"]))
        print("   ", (resultado["intentos"][-1]["sql"] or "")[:230])
        print("   ", str(resultado["filas"][:2])[:230])
    ataques = []
    for sql in ATAQUES:
        try:
            consultar_sql(escenario, sql)
            ataques.append({"sql": sql, "resultado": "EJECUTADA"})
        except ConsultaRechazada as exc:
            ataques.append({"sql": sql, "resultado": f"rechazada: {exc}"})
    memoria = ROOT / "storage/evidencias/fase4_memoria.sqlite3"
    catalogo = [{"nombre": h.name, "papel": PAPELES[h.name][0], "logica": PAPELES[h.name][1],
                 "descripcion": h.description,
                 "entradas": convert_to_openai_tool(h)["function"]["parameters"]["properties"]}
                for h in herramientas(escenario, memoria, "evidencia_fase4", "")]
    informe = {
        "fase": 4, "rubricas": ["R19", "R20", "R21"],
        "modo": "real remoto (OpenAI) para generar el SQL; ejecución local en solo lectura",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "esquema_permitido": ESQUEMA_PERMITIDO, "max_filas": MAX_FILAS,
        "r21_text_to_sql": consultas,
        "r21_consultas_hostiles_escritas_a_mano": ataques,
        "r19_catalogo_de_herramientas": catalogo,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ataques rechazados:", sum(a["resultado"].startswith("rechazada") for a in ataques),
          "de", len(ataques), "| guardado en", salida)


if __name__ == "__main__":
    main()
