"""Aviso de precio con el modelo real: consejo redactado por el LLM y verificado con NLI.

Requiere OPENAI_API_KEY. Para quince piezas con un aviso de precio, el modelo redacta un
consejo a partir de los hechos; se registra si pasa la verificación exacta y el NLI, o si queda
el aviso de plantilla. Después, una comparación completa en el chat. Catálogo sintético.
"""
import argparse
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Traza, crear_flujo
from pedro.catalog import crear_escenario
from pedro.contracts import Solicitud
from pedro.memory import nueva_sesion
from pedro.nli import MODELO, ModeloNLI
from pedro.precios import (UMBRAL_FUERTE, UMBRAL_NOTABLE, aconsejar, aviso_de_precio,
                           crear_consejero)
from pedro.verification import respuesta_local

ROOT = Path(__file__).resolve().parents[1]
CASOS = 15
EN_EL_CHAT = "Compara 5 unidades de PEC-02-0189"


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/precios_consejo_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    escenario = crear_escenario(ROOT / "storage/evidencias/precios_catalogos")
    llm = ChatOpenAI(model=modelo, temperature=0)
    consejero, nli = crear_consejero(llm), ModeloNLI()
    with sqlite3.connect(escenario.ruta) as db:
        ids = [fila[0] for fila in db.execute("SELECT id FROM parts ORDER BY id")]
    filas, fuentes, motivos = [], Counter(), Counter()
    total_recomendaciones = con_aviso = 0
    for producto_id in ids:
        comparacion = respuesta_local(escenario, Solicitud(producto_id=producto_id, cantidad=5))
        if comparacion.estado != "recomendacion":
            continue
        total_recomendaciones += 1
        if aviso_de_precio(comparacion) is None:
            continue
        con_aviso += 1
        if len(filas) >= CASOS:
            continue
        resultado = aconsejar(comparacion, consejero, nli)
        fuentes[resultado["fuente"]] += 1
        for error in resultado.get("errores") or []:
            motivos[error.split("(")[0].strip()] += 1
        filas.append({"producto_id": producto_id, "hechos": resultado["hechos"],
                      "aviso_de_plantilla": aviso_de_precio(comparacion),
                      "fuente_publicada": resultado["fuente"], "texto_publicado": resultado["texto"],
                      "consejo_rechazado": resultado.get("consejo_rechazado"),
                      "errores": resultado.get("errores")})
        print(producto_id, "->", resultado["fuente"], resultado.get("errores") or "")
        print("    ", (resultado.get("consejo_rechazado") or resultado["texto"])[:230])

    memoria = ROOT / f"storage/evidencias/precios_memoria-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.sqlite3"
    sesion = nueva_sesion(memoria, "evidencia_precios", escenario.dataset_id)
    traza = Traza()
    flujo = crear_flujo(escenario, memoria, llm=ChatOpenAI(model=modelo), clasificador=nli, traza=traza)
    respuesta = flujo.invoke({"input": EN_EL_CHAT}, config={"configurable": {
        "user_id": "evidencia_precios", "session_id": sesion}}).content
    print(respuesta)
    informe = {
        "tema": "aviso de precio", "rubricas_que_aplica": ["R04", "R06", "R09", "R11", "R12", "R19", "R24"],
        "modo": "real remoto (OpenAI) para el consejo; NLI real local; catálogo sintético",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0, "modelo_nli": MODELO,
        "umbrales": {"notable": UMBRAL_NOTABLE, "fuerte": UMBRAL_FUERTE},
        "frecuencia_del_aviso": {"recomendaciones_para_5_unidades": total_recomendaciones,
                                 "con_aviso_de_precio": con_aviso},
        "consejos": {"casos": len(filas), "publicado": dict(fuentes), "motivos_de_rechazo": dict(motivos)},
        "nota": "Los primeros quince casos con aviso, en orden de catálogo. Una corrida.",
        "casos": filas,
        "en_el_chat": {"usuario": EN_EL_CHAT, "respuesta_publicada": respuesta,
                       "consejo_precio": [e for e in traza.eventos if e["evento"] == "consejo_precio"],
                       "herramientas": [e["herramienta"] for e in traza.eventos if e["evento"] == "tool_start"]},
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(informe["frecuencia_del_aviso"], informe["consejos"]["publicado"], informe["consejos"]["motivos_de_rechazo"])
    print("guardado en", salida)


if __name__ == "__main__":
    main()
