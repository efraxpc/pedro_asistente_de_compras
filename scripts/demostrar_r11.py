"""R11: mide tres técnicas de prompt en la misma extracción: zero-shot, few-shot y few-shot + CoT.

Requiere OPENAI_API_KEY. Diez solicitudes difíciles, con la respuesta correcta fijada a mano.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.chains import crear_variantes_de_prompt

ROOT = Path(__file__).resolve().parents[1]
CAMPOS = ("producto_id", "cantidad", "presupuesto_centavos", "plazo_max_dias")
# solicitud -> (cantidad, presupuesto en centavos, plazo en días); None significa «no lo dice»
CASOS = [
    ("Necesito media docena de PEC-01-0001", "PEC-01-0001", 6, None, None),
    ("Compara PEC-02-0003, un par, hasta mil quinientos reales", "PEC-02-0003", 2, 150000, None),
    ("Quiero 3 de PEC-01-0002 para dentro de dos semanas", "PEC-01-0002", 3, None, 14),
    ("Dame 4 unidades de PEC-03-0001, sin límite de presupuesto, en 10 días", "PEC-03-0001", 4, None, 10),
    ("PEC-01-0001: dos unidades... no, mejor tres. Tope R$ 2.000", "PEC-01-0001", 3, 200000, None),
    ("¿Cuánto saldrían 5 PEC-04-0002 si no puedo gastar más de R$ 1.234,56?", "PEC-04-0002", 5, 123456, None),
    ("Compara PEC-05-0001 con R$ 800 de presupuesto", "PEC-05-0001", None, 80000, None),
    ("Necesito 10 PEC-06-0001 en una semana como máximo, gasto libre", "PEC-06-0001", 10, None, 7),
    ("Una docena de PEC-07-0001 por R$ 3 mil en un mes", "PEC-07-0001", 12, 300000, 30),
    ("Compra 2 de PEC-08-0001; el plazo me da igual y tengo R$ 0 disponibles", "PEC-08-0001", 2, 0, None),
]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/r11_prompts_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    variantes = crear_variantes_de_prompt(ChatOpenAI(model=modelo, temperature=0))
    entradas = [{"texto": caso[0]} for caso in CASOS]
    resumen: dict = {}
    detalle: list[dict] = []
    salidas = {nombre: cadena.batch(entradas, return_exceptions=True)
               for nombre, cadena in variantes.items()}
    for indice, (texto, *esperado) in enumerate(CASOS):
        fila: dict = {"solicitud": texto, "esperado": dict(zip(CAMPOS, esperado))}
        for nombre in variantes:
            resultado = salidas[nombre][indice]
            if isinstance(resultado, Exception):
                fila[nombre] = {"error": type(resultado).__name__, "campos_correctos": 0,
                                "todo_correcto": False}
                continue
            obtenido = {campo: getattr(resultado.solicitud, campo) for campo in CAMPOS}
            correctos = sum(obtenido[campo] == fila["esperado"][campo] for campo in CAMPOS)
            fila[nombre] = {"obtenido": obtenido, "campos_correctos": correctos,
                            "todo_correcto": correctos == len(CAMPOS),
                            "razonamiento": getattr(resultado, "razonamiento", None)}
        detalle.append(fila)
    for nombre in variantes:
        resumen[nombre] = {
            "solicitudes_correctas": f"{sum(f[nombre]['todo_correcto'] for f in detalle)}/{len(CASOS)}",
            "campos_correctos": f"{sum(f[nombre]['campos_correctos'] for f in detalle)}/{len(CASOS) * len(CAMPOS)}"}
    informe = {
        "rubrica": "R11", "modo": "real remoto (OpenAI); solicitudes sintéticas",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "nota": "Diez casos elegidos por difíciles y etiquetados a mano: no son una muestra representativa.",
        "resumen": resumen, "casos": detalle,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for fila in detalle:
        print(f"{fila['solicitud'][:58]:58}", {n: fila[n]["campos_correctos"] for n in variantes})
    print(json.dumps(resumen, ensure_ascii=False))
    print("guardado en", salida)


if __name__ == "__main__":
    main()
