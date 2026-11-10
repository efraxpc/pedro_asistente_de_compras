"""Fase 1 con el modelo real: plantilla, salida estructurada, invoke, batch y stream.

Requiere OPENAI_API_KEY. Llama a OpenAI; las solicitudes son sintéticas. No simula
resultados: si falta la clave, termina sin escribir nada.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.chains import PROMPT, crear_chain, crear_lcel

ROOT = Path(__file__).resolve().parents[1]
SOLICITUDES = [
    "Compara 2 unidades de PEC-01-0001 hasta R$ 5.000 en 7 días",
    "Necesito un termostato para nevera, sin prisa",
    "¿A qué ciudad corresponde el CEP 01001000?",
]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path,
                            default=ROOT / "docs/trazas/fase1_chain_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    nombre = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    modelo = ChatOpenAI(model=nombre, temperature=0)
    lcel, decorada = crear_lcel(modelo), crear_chain(modelo)
    entradas = [{"texto": texto} for texto in SOLICITUDES]

    uno = lcel.invoke(entradas[0])
    lote = lcel.batch(entradas)
    imperativa = decorada.invoke(entradas[0])
    fragmentos = [str(trozo.content) for trozo in (PROMPT.partial(formato="Responde en una frase.")
                                              | modelo).stream(entradas[1])]
    informe = {
        "fase": 1, "rubricas": ["R03", "R04", "R05", "R06"],
        "modo": "real remoto (OpenAI); solicitudes sintéticas",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": nombre, "temperature": 0,
        "plantilla": {"clase": type(PROMPT).__name__, "variables": sorted(PROMPT.input_variables),
                      "mensajes": [type(m).__name__ for m in PROMPT.messages]},
        "invoke_lcel": {"entrada": SOLICITUDES[0], "salida": uno.model_dump()},
        "invoke_chain_decorada": {"entrada": SOLICITUDES[0], "salida": imperativa.model_dump()},
        "batch_lcel": [{"entrada": texto, "salida": resultado.model_dump()}
                       for texto, resultado in zip(SOLICITUDES, lote)],
        "stream": {"entrada": SOLICITUDES[1], "fragmentos_recibidos": len(fragmentos),
                   "primeros_fragmentos": fragmentos[:8], "texto": "".join(fragmentos)},
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for texto, resultado in zip(SOLICITUDES, lote):
        print(texto, "->", resultado.intencion,
              resultado.solicitud.model_dump(exclude_none=True), "faltan", resultado.faltantes)
    print("stream:", len(fragmentos), "fragmentos |", "".join(fragmentos)[:90])
    print("guardado en", salida)


if __name__ == "__main__":
    main()
