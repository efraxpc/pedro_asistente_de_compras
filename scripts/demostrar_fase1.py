"""Fase 1 con el modelo real: plantilla, salida estructurada, invoke, batch y stream.

Requiere OPENAI_API_KEY. Llama a OpenAI; las solicitudes son sintéticas. No simula
resultados: si falta la clave, termina sin escribir nada.
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.chains import (PROMPT, crear_chain, crear_chain_robusta, crear_lcel,
                          crear_lcel_parcial)
from pedro.contracts import Extraccion
from pedro.laboratorio import DATOS, SOLICITUD, ensayar

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
    imperativa = decorada.invoke(entradas[0])
    # R05: las mismas tres entradas, una por una y en lote.
    inicio = time.perf_counter()
    en_serie = [lcel.invoke(entrada) for entrada in entradas]
    segundos_serie = time.perf_counter() - inicio
    inicio = time.perf_counter()
    lote = lcel.batch(entradas)
    segundos_lote = time.perf_counter() - inicio
    # R05: stream sobre una cadena que transmite (JSON parcial) y sobre una que no (Pydantic).
    inicio = time.perf_counter()
    estados, primer_estado = [], 0.0
    for estado in crear_lcel_parcial(modelo).stream(entradas[0]):
        if not estados:
            primer_estado = time.perf_counter() - inicio
        estados.append(estado)
    segundos_stream = time.perf_counter() - inicio
    fragmentos_pydantic = list(decorada.stream(entradas[0]))
    # R04: el modelo real repara salidas rotas emitidas por un generador doble.
    laboratorio = ensayar(modelo)
    for caso in laboratorio:
        obtenido = (caso["resultado"] or {}).get("solicitud", {})
        caso["datos_correctos"] = caso["capa_observada"] == "regla de dominio" or obtenido == DATOS
    # R04: la misma extracción con with_structured_output, sin parser ni instrucciones de formato.
    estructurado = [Extraccion.model_validate(salida) for salida in (
        PROMPT.partial(formato="") | modelo.with_structured_output(Extraccion)).batch(entradas)]
    # R05/R06: el mismo laboratorio con la cadena imperativa (@chain con try/except).
    laboratorio_imperativo = ensayar(modelo, crear_chain_robusta)
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
        "laboratorio_salidas_rotas": {
            "solicitud": SOLICITUD,
            "nota": "El generador es un doble que emite la salida rota; el reparador es el modelo real.",
            "casos": laboratorio},
        "with_structured_output": [
            {"entrada": texto, "salida": resultado.model_dump(),
             "igual_que_parser": resultado.solicitud == previo.solicitud
             and resultado.intencion == previo.intencion}
            for texto, resultado, previo in zip(SOLICITUDES, estructurado, lote)],
        "tiempos_invoke_y_batch": {
            "nota": "Una sola medición; depende de la red y del servicio. No es un benchmark.",
            "tres_invoke_en_serie_segundos": round(segundos_serie, 2),
            "un_batch_de_tres_segundos": round(segundos_lote, 2),
            "mismos_resultados": en_serie == lote},
        "stream": {
            "entrada": SOLICITUDES[0],
            "cadena_json_parcial": {
                "estados_recibidos": len(estados),
                "segundos_hasta_el_primero": round(primer_estado, 2),
                "segundos_totales": round(segundos_stream, 2),
                "muestra": [estados[i] for i in sorted({0, len(estados) // 3,
                                                        2 * len(estados) // 3, len(estados) - 1})]},
            "cadena_pydantic_con_chain": {
                "fragmentos_recibidos": len(fragmentos_pydantic),
                "nota": "El parser Pydantic necesita el JSON completo: emite un único fragmento."}},
        "laboratorio_con_chain_imperativa": {
            "misma_capa_que_la_declarativa": [c["capa_observada"] for c in laboratorio_imperativo]
            == [c["capa_observada"] for c in laboratorio],
            "datos_correctos": [c["capa_observada"] == "regla de dominio"
                                or (c["resultado"] or {}).get("solicitud", {}) == DATOS
                                for c in laboratorio_imperativo]},
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for texto, resultado in zip(SOLICITUDES, lote):
        print(texto, "->", resultado.intencion,
              resultado.solicitud.model_dump(exclude_none=True), "faltan", resultado.faltantes)
    for caso in laboratorio:
        print(f"  {caso['caso']:30} capa={caso['capa_observada']:17} "
              f"reparaciones={caso['reparaciones']} datos_correctos={caso['datos_correctos']}")
    print("with_structured_output igual que parser:",
          [c["igual_que_parser"] for c in informe["with_structured_output"]])
    print(f"invoke x3 en serie: {segundos_serie:.2f}s | batch de 3: {segundos_lote:.2f}s | "
          f"mismos resultados: {en_serie == lote}")
    print(f"stream JSON parcial: {len(estados)} estados, primero a los {primer_estado:.2f}s de "
          f"{segundos_stream:.2f}s | stream Pydantic: {len(fragmentos_pydantic)} fragmento")
    print("imperativa = declarativa en el laboratorio:",
          informe["laboratorio_con_chain_imperativa"]["misma_capa_que_la_declarativa"],
          informe["laboratorio_con_chain_imperativa"]["datos_correctos"])
    print("guardado en", salida)


if __name__ == "__main__":
    main()
