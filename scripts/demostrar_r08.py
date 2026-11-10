"""R08: agente ReAct clásico (initialize_agent) con el modelo real, herramientas y memoria.

Requiere OPENAI_API_KEY. Ejecuta la misma conversación de dos turnos dos veces: con el
historial dentro del prompt y sin él. El catálogo es sintético.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.catalog import crear_escenario
from pedro.legacy import crear_react_textual

ROOT = Path(__file__).resolve().parents[1]
TURNOS = ["Busca el compresor con SKU NEVE-COMP-0001 y dime su ID.",
          "¿Cuál de sus proveedores entrega más rápido y en cuántos días?"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/r08_react_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    escenario = crear_escenario(ROOT / "storage/evidencias/r08_catalogos")
    conversaciones = {}
    for nombre, con_memoria in (("con_historial_en_el_prompt", True),
                                ("sin_historial_en_el_prompt", False)):
        agente, memoria = crear_react_textual(ChatOpenAI(model=modelo, temperature=0), escenario,
                                              memoria_en_prompt=con_memoria)
        turnos = []
        for pregunta in TURNOS:
            resultado = agente.invoke({"input": pregunta})
            pasos: list[dict[str, str]] = [
                {"razonamiento_y_accion": accion.log.strip(), "herramienta": accion.tool,
                 "entrada": str(accion.tool_input), "observacion": str(observacion)[:400]}
                for accion, observacion in resultado["intermediate_steps"]]
            turnos.append({"pregunta": pregunta, "pasos": pasos, "respuesta": resultado["output"]})
            print(nombre, "|", pregunta, "->",
                  [paso["herramienta"] + "(" + paso["entrada"] + ")" for paso in pasos],
                  "|", str(resultado["output"])[:160])
        conversaciones[nombre] = {
            "variables_del_prompt": sorted(agente.agent.llm_chain.prompt.input_variables),
            "turnos": turnos,
            "memoria_guardada": memoria.load_memory_variables({})["chat_history"]}
    informe = {
        "rubrica": "R08", "modo": "real remoto (OpenAI); catálogo sintético",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "agente": "initialize_agent + AgentType.ZERO_SHOT_REACT_DESCRIPTION + ConversationBufferMemory",
        "herramientas": ["buscar_pieza", "ofertas_de_pieza"],
        "conversaciones": conversaciones,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("guardado en", salida)


if __name__ == "__main__":
    main()
