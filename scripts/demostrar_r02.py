"""R02: planificación con el modelo real. Guarda la trayectoria de herramientas observada.

Requiere OPENAI_API_KEY. Llama a OpenAI y a ViaCEP reales; el catálogo y las políticas son
sintéticos. No simula resultados: si falta la clave, termina sin escribir nada.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Traza, crear_flujo
from pedro.catalog import crear_escenario
from pedro.memory import nueva_sesion
from pedro.nli import MODELO, REVISION, ModeloNLI
from pedro.policy_demo import ORIGEN, crear_indice_demo

ROOT = Path(__file__).resolve().parents[1]
MIXTA = ("Compara 5 unidades de PEC-01-0001 con plazo de 7 días y dime qué dice la política de "
         "devoluciones sobre piezas dañadas, y confirma el CEP 01001000")
POR_TURNOS = ["Compara 5 unidades de PEC-01-0001 con plazo de 7 días",
              "¿Qué dice la política de devoluciones sobre piezas dañadas?",
              "Confirma el CEP 01001000",
              "ahora 6 unidades"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path,
                            default=ROOT / "docs/trazas/r02_planificacion_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    escenario = crear_escenario(ROOT / "storage/evidencias/r02_catalogos")
    memoria = ROOT / "storage/evidencias/r02_memoria.sqlite3"
    llm, nli, indice = ChatOpenAI(model=modelo), ModeloNLI(), crear_indice_demo()

    def conversar(turnos: list[str]) -> list[dict]:
        sesion = nueva_sesion(memoria, "evidencia_r02", escenario.dataset_id)
        traza = Traza()
        flujo = crear_flujo(escenario, memoria, llm=llm, clasificador=nli, indice=indice,
                            traza=traza)
        registro = []
        for pregunta in turnos:
            inicio = len(traza.eventos)
            respuesta = flujo.invoke({"input": pregunta}, config={"configurable": {
                "user_id": "evidencia_r02", "session_id": sesion}}).content
            eventos = traza.eventos[inicio:]
            registro.append({
                "pregunta": pregunta,
                "plan": next((e["peticiones"] for e in eventos if e["evento"] == "plan"), None),
                "herramientas": [{"nombre": e["herramienta"], "argumentos": e["entrada"]}
                                 for e in eventos if e["evento"] == "tool_start"],
                "errores_de_ejecucion": [e["tipo"] for e in eventos if "error" in e["evento"]],
                "verificaciones": [e["errores"] for e in eventos if e["evento"] == "verificacion"],
                "citas_ancladas": [c for e in eventos if e["evento"] == "citas_ancladas"
                                   for c in e["citas"]],
                "respuesta_publicada": respuesta,
            })
        return registro

    informe = {
        "rubrica": "R02",
        "modo": "real remoto (OpenAI y ViaCEP); NLI real local; datos sintéticos",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "modelo_nli": MODELO, "revision_nli": REVISION,
        "dataset_id": escenario.dataset_id, "origen_politicas": ORIGEN,
        "nota": "Cada turno admite hasta dos propuestas del agente; la lista de herramientas "
                "incluye las de ambas. La trayectoria depende del modelo y puede variar.",
    }
    bloques = {"solicitud_mixta_en_un_turno": conversar([MIXTA]),
               "solicitud_repartida_en_turnos": conversar(POR_TURNOS)}
    informe.update(bloques)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for bloque, turnos in bloques.items():
        print(bloque)
        for turno in turnos:
            print(" ", turno["pregunta"][:60], "->", [h["nombre"] for h in turno["herramientas"]])
            for linea in turno["respuesta_publicada"].splitlines()[:14]:
                print("    ", linea[:120])
    print("guardado en", salida)


if __name__ == "__main__":
    main()
