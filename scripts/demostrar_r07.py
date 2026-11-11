"""R07: el mismo agente en LangChain clásico y en LangGraph, con el modelo real.

Requiere OPENAI_API_KEY y el extra `comparacion` (uv sync --all-extras). Catálogo sintético.
"""
import argparse
import importlib.metadata as md
import inspect
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro import orquestadores
from pedro.catalog import crear_escenario

ROOT = Path(__file__).resolve().parents[1]
TURNOS = ["Busca el compresor con SKU NEVE-COMP-0001 y dime su ID.",
          "¿Cuál de sus proveedores entrega más rápido y en cuántos días?",
          "¿Y cuál es el más barato con stock? Dime el precio en reales."]
OTRO_HILO = "¿De qué pieza estábamos hablando?"


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/r07_orquestadores_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    escenario = crear_escenario(ROOT / "storage/evidencias/r07_catalogos")
    resultados = {}
    for nombre, constructor in (("LangChain clásico", orquestadores.agente_langchain),
                                ("LangGraph", orquestadores.agente_langgraph)):
        conversar = constructor(ChatOpenAI(model=modelo, temperature=0), escenario)
        turnos = []
        inicio = time.perf_counter()
        for texto in TURNOS:
            turno = conversar(texto, "hilo-a")
            turnos.append({"usuario": texto, **turno})
            print(f"{nombre:18} | {texto[:44]:44} -> {turno['herramientas']} | {turno['respuesta'][:100]}")
        segundos = time.perf_counter() - inicio
        aislado = conversar(OTRO_HILO, "hilo-b")
        print(f"{nombre:18} | otro hilo: {aislado['respuesta'][:110]}")
        grafo = getattr(conversar, "grafo", None)
        resultados[nombre] = {
            "lineas_para_construirlo": len(inspect.getsource(constructor).splitlines()),
            "memoria": ("RunnableWithMessageHistory + historial por session_id"
                        if grafo is None else "checkpointer InMemorySaver + thread_id"),
            "nodos_del_grafo": None if grafo is None else sorted(grafo.get_graph().nodes),
            "segundos_tres_turnos": round(segundos, 1),
            "turnos": turnos, "otro_hilo": {"usuario": OTRO_HILO, **aislado}}
    informe = {
        "rubrica": "R07", "modo": "real remoto (OpenAI); catálogo sintético",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "versiones": {p: md.version(p) for p in ("langchain-core", "langchain-classic",
                                                 "langchain", "langgraph")},
        "nota": "Mismo modelo, mismas dos herramientas y mismo prompt. Una ejecución por "
                "orquestador: los tiempos no son un benchmark.",
        "orquestadores": resultados,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({n: (r["lineas_para_construirlo"], r["segundos_tres_turnos"], r["nodos_del_grafo"])
           for n, r in resultados.items()})
    print("guardado en", salida)


if __name__ == "__main__":
    main()
