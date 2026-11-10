"""Evaluación remota del mismo flujo final usado por Streamlit."""
import argparse
import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client, evaluate

from pedro.agent import Traza, crear_flujo
from pedro.catalog import SOURCE, crear_escenario
from pedro.memory import nueva_sesion
from pedro.nli import MODELO, REVISION, ModeloNLI

CASOS_RUTA = Path("evals/casos_derivados.json")


def referencias() -> list[dict]:
    dato = json.loads(CASOS_RUTA.read_text(encoding="utf-8"))
    if dato["tipo"] != "derivados_sinteticos_no_oficiales" or len(dato["casos"]) != 30:
        raise ValueError("se requieren 30 casos derivados congelados")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != dato["fuente_sha256"]:
        raise ValueError("las referencias pertenecen a otra versión del catálogo")
    return dato["casos"]


def _salida(run) -> dict:
    return run.outputs or {}


def evaluar_contenido(run, example):
    esperado = example.outputs or {}
    texto = str(_salida(run).get("respuesta", ""))
    return {"key": "contenido", "score": int(esperado["contiene"] in texto)
            if "contiene" in esperado else None}


def evaluar_ganador(run, example):
    esperado = example.outputs or {}
    if esperado.get("estado") != "recomendacion":
        return {"key": "ganador", "score": None}
    texto = str(_salida(run).get("respuesta", ""))
    return {"key": "ganador", "score": int(esperado["fuente_ganadora"] in texto)}


def evaluar_importe(run, example):
    esperado = example.outputs or {}
    if esperado.get("estado") != "recomendacion":
        return {"key": "importe", "score": None}
    texto = str(_salida(run).get("respuesta", ""))
    return {"key": "importe", "score": int(esperado["total_brl"] in texto)}


def evaluar_trayectoria(run, example):
    esperado = example.outputs or {}
    llamadas = _salida(run).get("herramientas", [])
    return {"key": "trayectoria", "score": int(all(
        herramienta in llamadas for herramienta in esperado["herramientas"]))}


def evaluar_herramienta_decisiva(run, example):
    """Trayectoria mínima: se llamó a la herramienta que produce la respuesta (la última esperada)."""
    esperadas = (example.outputs or {})["herramientas"]
    if not esperadas:
        return {"key": "herramienta_decisiva", "score": None}
    return {"key": "herramienta_decisiva",
            "score": int(esperadas[-1] in _salida(run).get("herramientas", []))}


def evaluar_primera_propuesta(run, example):
    """Entre los casos que pasan por el agente, la primera propuesta superó la verificación."""
    intentos = _salida(run).get("verificaciones", [])
    if not intentos:
        return {"key": "primera_propuesta", "score": None}
    return {"key": "primera_propuesta", "score": int(not intentos[0]["errores"])}


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--modelo", help="modelo de OpenAI; por defecto PEDRO_MODEL o gpt-4.1-mini")
    argumentos.add_argument("--salida", type=Path, help="copia versionable del registro")
    opciones = argumentos.parse_args()
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("LANGSMITH_API_KEY"):
        raise SystemExit("Faltan OPENAI_API_KEY y LANGSMITH_API_KEY; sin evaluación remota")
    from langchain_openai import ChatOpenAI
    casos = referencias()
    escenario = crear_escenario(Path("storage/evals/catalogos"))
    memoria = Path("storage/evals/memoria.sqlite3")
    modelo = opciones.modelo or os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    llm = ChatOpenAI(model=modelo)
    llm.invoke("ping")  # falla aquí, y no en cada caso, si el modelo no está disponible
    nli = ModeloNLI()

    def objetivo(entrada: dict) -> dict:
        sesion = nueva_sesion(memoria, "evaluacion", escenario.dataset_id)
        traza = Traza()
        flujo = crear_flujo(escenario, memoria, llm=llm, clasificador=nli, traza=traza)
        salida = flujo.invoke({"input": entrada["pregunta"]}, config={"configurable": {
            "user_id": "evaluacion", "session_id": sesion}})
        return {"respuesta": salida.content,
                "herramientas": [e["herramienta"] for e in traza.eventos
                                 if e["evento"] == "tool_start"],
                "verificaciones": [{"intento": e["intento"], "estado": e["estado"],
                                    "errores": e["errores"]}
                                   for e in traza.eventos if e["evento"] == "verificacion"]}

    ahora = datetime.now(timezone.utc)
    # LangSmith necesita que el conjunto de casos exista allí; se crea una vez y se reutiliza.
    cliente = Client()
    huella = hashlib.sha256(CASOS_RUTA.read_bytes()).hexdigest()[:8]
    nombre_dataset = f"pedro-infnet-casos-derivados-{huella}"
    if not cliente.has_dataset(dataset_name=nombre_dataset):
        dataset = cliente.create_dataset(
            dataset_name=nombre_dataset,
            description="30 casos derivados sintéticos y congelados; no son los casos oficiales.")
        cliente.create_examples(dataset_id=dataset.id, examples=[
            {"inputs": {"pregunta": caso["pregunta"]}, "outputs": caso["esperado"],
             "metadata": {"grupo": caso["grupo"], "caso_id": caso["id"]}} for caso in casos])
    experimento = evaluate(
        objetivo, data=nombre_dataset, evaluators=[evaluar_contenido, evaluar_ganador,
        evaluar_importe, evaluar_trayectoria, evaluar_herramienta_decisiva,
        evaluar_primera_propuesta], upload_results=True, max_concurrency=1,
        experiment_prefix=f"pedro-infnet-flujo-{modelo}",
        metadata={"dataset_id": escenario.dataset_id, "nli_model": MODELO,
                  "nli_revision": REVISION, "casos": len(casos), "modelo_llm": modelo})
    resultados = list(experimento)
    filas = []
    metricas: dict[str, list[int]] = {}
    por_grupo: dict[str, dict[str, list[int]]] = {}
    for fila in resultados:
        scores = {r.key: r.score for r in fila["evaluation_results"]["results"]}
        meta_caso = fila["example"].metadata or {}
        grupo = str(meta_caso.get("grupo"))
        for nombre, score in scores.items():
            if score is not None:
                metricas.setdefault(nombre, []).append(int(score))
                por_grupo.setdefault(grupo, {}).setdefault(nombre, []).append(int(score))
        filas.append({"caso_id": meta_caso.get("caso_id"),
                      "pregunta": (fila["example"].inputs or {}).get("pregunta"),
                      "grupo": meta_caso.get("grupo"),
                      "run_id": str(fila["run"].id), "salida": fila["run"].outputs,
                      "scores": scores})
    resumen = {k: {"aciertos": sum(v), "total": len(v),
                   "tasa": sum(v) / len(v) if v else None}
               for k, v in metricas.items()}
    destino = Path("storage/evals/flujo.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    registro = json.dumps({
        "fecha_utc": ahora.isoformat(), "modo": "real", "modelo_llm": modelo,
        "experimento_langsmith": experimento.experiment_name,
        "dataset_langsmith": nombre_dataset,
        "dataset_id": escenario.dataset_id, "resumen": resumen,
        "por_grupo": {grupo: {nombre: f"{sum(v)}/{len(v)}" for nombre, v in metricas_grupo.items()}
                      for grupo, metricas_grupo in por_grupo.items()},
        "casos": filas}, indent=2, ensure_ascii=False)
    destino.write_text(registro, encoding="utf-8")
    if opciones.salida:
        opciones.salida.parent.mkdir(parents=True, exist_ok=True)
        opciones.salida.write_text(registro + "\n", encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False))
    print(f"experimento {experimento.experiment_name}; registro {opciones.salida or destino}")


if __name__ == "__main__":
    main()
