"""R17: compara las reglas del chat con el intérprete con modelo en mensajes difíciles.

Requiere OPENAI_API_KEY. Cada caso parte de una solicitud en curso (o de ninguna) y tiene el
resultado correcto fijado a mano: si es una compra y cómo debe quedar la solicitud.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.catalog import crear_escenario
from pedro.contracts import Solicitud
from pedro.dialogue import EstadoCompra, crear_interprete, interpretar_compra, interpretar_turno

ROOT = Path(__file__).resolve().parents[1]
EN_CURSO = {"producto_id": "PEC-01-0001", "cantidad": 2, "plazo_max_dias": 7}
# (hay solicitud en curso, mensaje, resultado esperado: None = no es compra;
#  si no, (cantidad, presupuesto_centavos, plazo_max_dias))
CASOS = [
    (True, "Ahora que sean 3 y mantén el plazo", (3, None, 7)),
    (True, "Súbelo a media docena", (6, None, 7)),
    (True, "Con cuatro me alcanza", (4, None, 7)),
    (True, "Mejor sin límite de plazo, pero no puedo pasar de R$ 5.000", (2, 500000, None)),
    (True, "Necesito que llegue en dos semanas como mucho", (2, None, 14)),
    (True, "Olvida el plazo", (2, None, None)),
    (True, "Duplica la cantidad", (4, None, 7)),
    (True, "Tengo mil quinientos reales para esto", (2, 150000, 7)),
    (True, "¿Cómo se comprueba la compatibilidad eléctrica antes de instalar una pieza?", None),
    (True, "¿La garantía cubre dos piezas del mismo pedido?", None),
    (True, "¿A qué ciudad corresponde el CEP 01001000?", None),
    (True, "Gracias, eso es todo", None),
    (False, "Compara un par de PEC-01-0002 en 10 días", (2, None, 10)),
    (False, "Compara PEC-01-0001", (None, None, None)),
]


def _resumen(resultado) -> tuple | None:
    if resultado is None:
        return None
    solicitud = resultado[0].solicitud
    return (solicitud.cantidad, solicitud.presupuesto_centavos, solicitud.plazo_max_dias)


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/r17_interprete_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    escenario = crear_escenario(ROOT / "storage/evidencias/r17_catalogos")
    interprete = crear_interprete(ChatOpenAI(model=modelo, temperature=0))
    filas = []
    aciertos = {"reglas": 0, "reglas_y_modelo": 0}
    for hay_previo, mensaje, esperado in CASOS:
        previo = (EstadoCompra(solicitud=Solicitud.model_validate(EN_CURSO)) if hay_previo else None)
        reglas = _resumen(interpretar_compra(escenario, previo, mensaje))
        combinado, informe = interpretar_turno(escenario, previo, mensaje, interprete)
        con_modelo = _resumen(combinado)
        aciertos["reglas"] += reglas == esperado
        aciertos["reglas_y_modelo"] += con_modelo == esperado
        filas.append({"solicitud_en_curso": EN_CURSO if hay_previo else None, "mensaje": mensaje,
                      "esperado": esperado, "reglas": reglas, "reglas_y_modelo": con_modelo,
                      "lectura_del_modelo": informe.get("modelo")})
        print(f"{mensaje[:62]:62} esperado={str(esperado):22} reglas={str(reglas):22} "
              f"{'✔' if reglas == esperado else '✘'}  +modelo={str(con_modelo):22} "
              f"{'✔' if con_modelo == esperado else '✘'}")
    informe_final = {
        "rubrica": "R17", "modo": "real remoto (OpenAI) para el intérprete; reglas locales",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "nota": "Catorce mensajes elegidos por difíciles y etiquetados a mano. Cada resultado es "
                "None (no es compra) o (cantidad, presupuesto en centavos, plazo en días).",
        "aciertos": {nombre: f"{valor}/{len(CASOS)}" for nombre, valor in aciertos.items()},
        "casos": filas,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe_final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("aciertos", informe_final["aciertos"], "| guardado en", salida)


if __name__ == "__main__":
    main()
