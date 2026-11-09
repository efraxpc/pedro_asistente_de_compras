"""Evaluación remota del mismo flujo final usado por Streamlit."""
import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langsmith import evaluate
from langsmith.schemas import Example

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


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("LANGSMITH_API_KEY"):
        raise SystemExit("Faltan OPENAI_API_KEY y LANGSMITH_API_KEY; sin evaluación remota")
    from langchain_openai import ChatOpenAI
    casos = referencias()
    escenario = crear_escenario(Path("storage/evals/catalogos"))
    memoria = Path("storage/evals/memoria.sqlite3")
    llm = ChatOpenAI(model=os.getenv("PEDRO_MODEL", "gpt-4.1-mini"))
    nli = ModeloNLI()

    def objetivo(entrada: dict) -> dict:
        sesion = nueva_sesion(memoria, "evaluacion", escenario.dataset_id)
        traza = Traza()
        flujo = crear_flujo(escenario, memoria, llm=llm, clasificador=nli, traza=traza)
        salida = flujo.invoke({"input": entrada["pregunta"]}, config={"configurable": {
            "user_id": "evaluacion", "session_id": sesion}})
        return {"respuesta": salida.content,
                "herramientas": [e["herramienta"] for e in traza.eventos
                                 if e["evento"] == "tool_start"]}

    ahora = datetime.now(timezone.utc)
    dataset = uuid4()
    ejemplos = [Example(id=uuid4(), dataset_id=dataset, created_at=ahora,
                        inputs={"pregunta": caso["pregunta"]}, outputs=caso["esperado"],
                        metadata={"grupo": caso["grupo"], "caso_id": caso["id"],
                                  "dataset_id": escenario.dataset_id}) for caso in casos]
    resultados = list(evaluate(
        objetivo, data=ejemplos, evaluators=[evaluar_contenido, evaluar_ganador,
        evaluar_importe, evaluar_trayectoria], upload_results=True, max_concurrency=1,
        experiment_prefix="pedro-infnet-flujo",
        metadata={"dataset_id": escenario.dataset_id, "nli_model": MODELO,
                  "nli_revision": REVISION, "casos": len(casos)}))
    filas = []
    metricas: dict[str, list[int]] = {}
    for fila in resultados:
        scores = {r.key: r.score for r in fila["evaluation_results"]["results"]}
        meta_caso = fila["example"].metadata or {}
        for nombre, score in scores.items():
            if score is not None:
                metricas.setdefault(nombre, []).append(int(score))
        filas.append({"caso_id": meta_caso.get("caso_id"),
                      "grupo": meta_caso.get("grupo"),
                      "run_id": str(fila["run"].id), "salida": fila["run"].outputs,
                      "scores": scores})
    resumen = {k: {"aciertos": sum(v), "total": len(v),
                   "tasa": sum(v) / len(v) if v else None}
               for k, v in metricas.items()}
    destino = Path("storage/evals/flujo.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"fecha_utc": ahora.isoformat(), "modo": "real",
                                   "dataset_id": escenario.dataset_id, "resumen": resumen,
                                   "casos": filas}, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False))
    print(f"registro {destino}")


if __name__ == "__main__":
    main()
