"""R10: el agente llama a una API externa real (ViaCEP) por function calling.

Requiere OPENAI_API_KEY y acceso a viacep.com.br. Guarda el esquema que recibe el modelo,
los argumentos que el modelo envía, la respuesta de la API y lo que se publica.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.utils.function_calling import convert_to_openai_tool

from pedro.agent import Traza, crear_flujo, herramientas
from pedro.catalog import crear_escenario
from pedro.memory import nueva_sesion
from pedro.nli import ModeloNLI

ROOT = Path(__file__).resolve().parents[1]
PREGUNTAS = ["Voy a recibir el pedido en el CEP 01001000. ¿A qué ciudad y estado corresponde?",
             "¿Y el CEP 99999999?",
             "¿Y el CEP 123?"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/r10_viacep_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    escenario = crear_escenario(ROOT / "storage/evidencias/r10_catalogos")
    memoria = ROOT / "storage/evidencias/r10_memoria.sqlite3"
    herramienta = next(h for h in herramientas(escenario, memoria, "evidencia_r10", "")
                       if h.name == "consultar_cep")
    sesion = nueva_sesion(memoria, "evidencia_r10", escenario.dataset_id)
    traza = Traza()
    flujo = crear_flujo(escenario, memoria, llm=ChatOpenAI(model=modelo), clasificador=ModeloNLI(),
                        traza=traza)
    turnos = []
    for pregunta in PREGUNTAS:
        desde = len(traza.eventos)
        respuesta = flujo.invoke({"input": pregunta}, config={"configurable": {
            "user_id": "evidencia_r10", "session_id": sesion}}).content
        eventos = traza.eventos[desde:]
        llamadas = [{"herramienta": inicio["herramienta"], "argumentos_del_modelo": inicio["entrada"],
                     "respuesta_de_la_api": fin["resultado"]}
                    for inicio, fin in zip([e for e in eventos if e["evento"] == "tool_start"],
                                           [e for e in eventos if e["evento"] == "tool_end"])]
        turnos.append({"pregunta": pregunta, "llamadas": llamadas,
                       "verificaciones": [{"intento": e["intento"], "errores": e["errores"]}
                                          for e in eventos if e["evento"] == "verificacion"],
                       "respuesta_publicada": respuesta})
        print(pregunta, "->", [(c["argumentos_del_modelo"], c["respuesta_de_la_api"][:90])
                               for c in llamadas], "|", str(respuesta)[:90])
    informe = {
        "rubrica": "R10", "modo": "real remoto: OpenAI y ViaCEP (https://viacep.com.br)",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo,
        "esquema_enviado_al_modelo": convert_to_openai_tool(herramienta),
        "turnos": turnos,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("guardado en", salida)


if __name__ == "__main__":
    main()
