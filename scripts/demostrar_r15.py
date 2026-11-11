"""R15: la misma conversación con la memoria propia de Pedro y con LangMem.

Requiere OPENAI_API_KEY y el extra `comparacion`. Compara qué guarda cada una, quién decide
guardarlo y qué se recupera en otra sesión y para otro usuario. Catálogo sintético.
"""
import argparse
import importlib.metadata as md
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Traza, crear_flujo
from pedro.catalog import crear_escenario
from pedro.memory import MODELO_RECUERDOS, nueva_sesion, preferencias
from pedro.nli import ModeloNLI
from pedro.orquestadores import agente_con_langmem

ROOT = Path(__file__).resolve().parents[1]
SESION_1 = ["Prefiero proveedores nacionales, recuérdalo.",
            "Compara 2 unidades de PEC-01-0001 con plazo de 7 días.",
            "Uf, creo que ese compresor me va a salir caro. Mi taller es pequeño."]
SESION_2 = "¿Qué recuerdas de mis preferencias?"


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/r15_memoria_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    escenario = crear_escenario(ROOT / "storage/evidencias/r15_catalogos")

    # --- Memoria propia de Pedro ---
    memoria = ROOT / f"storage/evidencias/r15_memoria-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.sqlite3"
    traza = Traza()
    flujo = crear_flujo(escenario, memoria, llm=ChatOpenAI(model=modelo), clasificador=ModeloNLI(),
                        traza=traza)
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    turnos_pedro = []
    for texto in SESION_1:
        desde = len(traza.eventos)
        respuesta = flujo.invoke({"input": texto}, config={"configurable": {
            "user_id": "ana", "session_id": sesion}}).content
        turnos_pedro.append({"usuario": texto, "respuesta": respuesta.splitlines()[0],
                             "herramientas": [e["herramienta"] for e in traza.eventos[desde:]
                                              if e["evento"] == "tool_start"]})
        print("Pedro   |", texto[:50], "->", turnos_pedro[-1]["herramientas"], "|", respuesta.splitlines()[0][:90])
    nueva_sesion(memoria, "luis", escenario.dataset_id)
    with sqlite3.connect(memoria) as db:
        episodios = [fila[0][:140] for fila in db.execute(
            "SELECT texto FROM episodios WHERE user_id='ana' ORDER BY id")]
    pedro = {"turnos": turnos_pedro,
             "guardado_para_ana": {"preferencias": preferencias(memoria, "ana"), "episodios": episodios},
             "guardado_para_otro_usuario": {"preferencias": preferencias(memoria, "luis")},
             "quien_decide": "el código: una preferencia solo con cita literal del usuario; un "
                             "episodio solo tras una respuesta de compra verificada"}

    # --- LangMem ---
    embeddings = FastEmbedEmbeddings(model_name=MODELO_RECUERDOS, doc_embed_type="passage")
    conversar, almacen = agente_con_langmem(ChatOpenAI(model=modelo, temperature=0), escenario,
                                            embeddings, 384)
    turnos_langmem = []
    for texto in SESION_1:
        turno = conversar(texto, "ana", "sesion-1")
        turnos_langmem.append({"usuario": texto, **turno})
        print("LangMem |", texto[:50], "->", [h.split("(")[0] for h in turno["herramientas"]], "|",
              turno["respuesta"][:90])
    otra_sesion = conversar(SESION_2, "ana", "sesion-2")
    otro_usuario = conversar(SESION_2, "luis", "sesion-3")
    print("LangMem | sesión nueva:", otra_sesion["respuesta"][:160])
    print("LangMem | otro usuario:", otro_usuario["respuesta"][:160])
    langmem = {"turnos": turnos_langmem,
               "guardado_para_ana": [item.value for item in almacen.search(("recuerdos", "ana"))],
               "guardado_para_otro_usuario": [item.value for item in almacen.search(("recuerdos", "luis"))],
               "sesion_nueva": {"usuario": SESION_2, **otra_sesion},
               "otro_usuario": {"usuario": SESION_2, **otro_usuario},
               "quien_decide": "el modelo, con las herramientas manage_memory y search_memory"}
    print("Pedro guardó:", pedro["guardado_para_ana"]["preferencias"], "y", len(episodios), "episodio(s)")
    print("LangMem guardó:", langmem["guardado_para_ana"])

    informe = {
        "rubrica": "R15", "modo": "real remoto (OpenAI); embeddings reales locales; catálogo sintético",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo,
        "versiones": {p: md.version(p) for p in ("langmem", "langgraph", "langchain")},
        "nota": "La misma conversación de tres mensajes en los dos sistemas. Una ejecución: lo que "
                "el modelo decide guardar con LangMem puede variar de una corrida a otra.",
        "memoria_propia_de_pedro": pedro, "langmem": langmem,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("guardado en", salida)


if __name__ == "__main__":
    main()
