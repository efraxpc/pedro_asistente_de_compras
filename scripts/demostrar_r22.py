"""R22: agente de recuperación sobre el índice FAISS ya guardado en knowledge/politicas/.

No construye el índice: lo carga con `cargar_indice` tras comprobar el manifiesto y las
huellas. Requiere OPENAI_API_KEY para las preguntas al agente; el corpus es ficticio.
"""
import argparse
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Traza, crear_flujo, herramientas
from pedro.catalog import crear_escenario
from pedro.memory import nueva_sesion
from pedro.nli import ModeloNLI
from pedro.rag import cargar_indice, inspeccionar_indice

ROOT = Path(__file__).resolve().parents[1]
CARPETA = ROOT / "knowledge/politicas"
PREGUNTAS = ["¿Cómo se comprueba la compatibilidad eléctrica antes de instalar una pieza?",
             "¿Se puede mandar en varias cajas?"]


def _error(accion) -> str:
    try:
        accion()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return "sin error"


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path,
                            default=ROOT / "docs/trazas/r22_indice_existente.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_openai import ChatOpenAI

    manifiesto = inspeccionar_indice(CARPETA)
    embeddings = FastEmbedEmbeddings(model_name=manifiesto["embedding_model"],
                                     doc_embed_type="passage")
    # La puerta de seguridad: sin confianza explícita o con un archivo alterado, no se carga.
    sin_confianza = _error(lambda: cargar_indice(CARPETA, embeddings, origen_confiable=False))
    with tempfile.TemporaryDirectory() as temporal:
        copia = Path(temporal) / "politicas"
        shutil.copytree(CARPETA, copia)
        with (copia / "index.pkl").open("ab") as archivo:
            archivo.write(b"alterado")
        alterado = _error(lambda: cargar_indice(copia, embeddings, origen_confiable=True))

    inicio = time.perf_counter()
    indice, _ = cargar_indice(CARPETA, embeddings, origen_confiable=True)
    segundos_carga = time.perf_counter() - inicio

    escenario = crear_escenario(ROOT / "storage/evidencias/r22_catalogos")
    memoria = ROOT / "storage/evidencias/r22_memoria.sqlite3"
    herramienta = next(h for h in herramientas(escenario, memoria, "evidencia_r22", "", indice)
                       if h.name == "consultar_politicas")
    directa = json.loads(herramienta.invoke({"pregunta": PREGUNTAS[0]}))

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    sesion = nueva_sesion(memoria, "evidencia_r22", escenario.dataset_id)
    traza = Traza()
    flujo = crear_flujo(escenario, memoria, llm=ChatOpenAI(model=modelo), clasificador=ModeloNLI(),
                        indice=indice, traza=traza)
    turnos = []
    for pregunta in PREGUNTAS:
        desde = len(traza.eventos)
        respuesta = flujo.invoke({"input": pregunta}, config={"configurable": {
            "user_id": "evidencia_r22", "session_id": sesion}}).content
        eventos = traza.eventos[desde:]
        turnos.append({
            "pregunta": pregunta,
            "herramientas": [e["herramienta"] for e in eventos if e["evento"] == "tool_start"],
            "citas_ancladas": [c for e in eventos if e["evento"] == "citas_ancladas"
                               for c in e["citas"]],
            "respuesta_publicada": respuesta})

    informe = {
        "rubrica": "R22",
        "modo": "índice cargado de disco; agente real remoto (OpenAI); NLI real local; corpus ficticio",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "indice": {"carpeta": str(CARPETA.relative_to(ROOT)), "origen": manifiesto["origen"],
                   "creado_utc": manifiesto.get("creado_utc"),
                   "embedding_model": manifiesto["embedding_model"],
                   "dimension": manifiesto["dimension"], "metrica": manifiesto["metrica"],
                   "fragmentos": indice.index.ntotal, "sha256": manifiesto["sha256"],
                   "segundos_de_carga": round(segundos_carga, 2)},
        "puerta_de_seguridad": {"sin_confianza_explicita": sin_confianza,
                                "copia_con_index_pkl_alterado": alterado},
        "herramienta_consultar_politicas": {
            "pregunta": PREGUNTAS[0],
            "fragmentos": [{"posicion": f["posicion"], "fuente_id": f["fuente_id"],
                            "seccion": f["metadatos"]["seccion"], "distancia_l2": round(f["score"], 3)}
                           for f in directa["fragmentos"]]},
        "agente": {"modelo_llm": modelo, "turnos": turnos},
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("carga:", informe["indice"]["fragmentos"], "fragmentos en", informe["indice"]["segundos_de_carga"], "s")
    print("puerta:", sin_confianza, "|", alterado)
    print("herramienta:", [f["fuente_id"] for f in informe["herramienta_consultar_politicas"]["fragmentos"]])
    for turno in turnos:
        print(turno["pregunta"], "->", turno["herramientas"], turno["citas_ancladas"])
        print("   ", str(turno["respuesta_publicada"])[:260].replace("\n", " / "))
    print("guardado en", salida)


if __name__ == "__main__":
    main()
