"""R09: routing dinámico con RouterChain. Compara el router por reglas con el router LLM.

Requiere OPENAI_API_KEY. El catálogo es sintético y ViaCEP se simula.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.catalog import crear_escenario
from pedro.legacy import DESTINOS, RouterCompras, crear_router_llm, ejecutar_ruta

ROOT = Path(__file__).resolve().parents[1]
# pregunta -> ruta que un humano elegiría
CASOS = [
    ("precio de PEC-01-0001", "comparacion"),
    ("Busca compresores para nevera", "catalogo"),
    ("¿Cuánto cuesta el compresor PEC-01-0001?", "comparacion"),
    ("¿Quién vende PEC-01-0001 y en cuántos días llega?", "comparacion"),
    ("¿A qué ciudad corresponde el CEP 01001-000?", "cep"),
    ("¿Tienen en stock algún termostato?", "catalogo"),
    ("Hola, buenos días", "aclaracion"),
]


def _resumen(resultado) -> str:
    if isinstance(resultado, list):
        return f"{len(resultado)} filas"
    return str(resultado)[:80]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/r09_router_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    escenario = crear_escenario(ROOT / "storage/evidencias/r09_catalogos")
    routers = {"reglas": RouterCompras(),
               "llm": crear_router_llm(ChatOpenAI(model=modelo, temperature=0))}
    filas = []
    aciertos = {nombre: 0 for nombre in routers}
    for pregunta, esperada in CASOS:
        fila: dict[str, str] = {"pregunta": pregunta, "ruta_esperada": esperada}
        for nombre, router in routers.items():
            ejecucion = ejecutar_ruta(router, escenario, pregunta)
            fila[f"ruta_{nombre}"] = ejecucion["ruta"]
            fila[f"resultado_{nombre}"] = _resumen(ejecucion["resultado"])
            aciertos[nombre] += ejecucion["ruta"] == esperada
        filas.append(fila)
        print(f"{pregunta:52} esperada={esperada:11} reglas={fila['ruta_reglas']:11} llm={fila['ruta_llm']}")
    informe = {
        "rubrica": "R09", "modo": "router LLM real remoto (OpenAI); router por reglas local; ViaCEP simulado",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0, "destinos": DESTINOS,
        "nota": "Las rutas esperadas las fijó una persona. Siete casos no son una medida de exactitud.",
        "aciertos": {nombre: f"{valor}/{len(CASOS)}" for nombre, valor in aciertos.items()},
        "casos": filas,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("aciertos", informe["aciertos"], "| guardado en", salida)


if __name__ == "__main__":
    main()
