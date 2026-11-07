"""Evaluación offline de componentes con LangSmith SDK, sin subir resultados.

Usa solo la fixture explícita del enunciado; no representa los 20 casos del kit.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from langsmith import evaluate
from langsmith.schemas import Example

from compraslab.business import comparar_ofertas
from compraslab.schemas import Oferta, SolicitudCompra


OFERTAS = [
    dict(dataset_id="fixture_prompt", id="A", producto_id="PROD-003", proveedor_id="A",
         proveedor_nombre="Demo A", precio_unitario_centavos=48000,
         flete_centavos=20000, stock=30, plazo_dias=12),
    dict(dataset_id="fixture_prompt", id="B", producto_id="PROD-003", proveedor_id="B",
         proveedor_nombre="Demo B", precio_unitario_centavos=52000,
         flete_centavos=15000, stock=25, plazo_dias=5),
    dict(dataset_id="fixture_prompt", id="C", producto_id="PROD-003", proveedor_id="C",
         proveedor_nombre="Demo C", precio_unitario_centavos=50000,
         flete_centavos=10000, stock=10, plazo_dias=3),
]


def objetivo(entradas: dict) -> dict:
    solicitud = SolicitudCompra(**entradas["solicitud"])
    if solicitud.faltantes():
        return {"estado": "aclaracion", "faltantes": solicitud.faltantes()}
    alternativas = comparar_ofertas(solicitud, [Oferta(**o) for o in OFERTAS])
    validas = [a for a in alternativas if a.cumple]
    if not validas:
        return {"estado": "sin_oferta"}
    return {"estado": "recomendacion", "proveedor": validas[0].oferta.proveedor_id,
            "total_centavos": validas[0].total_centavos}


def evaluador(run, example):
    return {"key": "resultado_exacto", "score": int(run.outputs == example.outputs)}


def main() -> None:
    casos = [
        ("referencia_del_prompt", {"producto_id": "PROD-003", "cantidad": 20,
                                  "presupuesto_centavos": 1200000, "plazo_max_dias": 7},
         {"estado": "recomendacion", "proveedor": "B", "total_centavos": 1055000}),
        ("faltante", {"producto_id": "PROD-003", "presupuesto_centavos": 1200000,
                      "plazo_max_dias": 7},
         {"estado": "aclaracion", "faltantes": ["cantidad"]}),
        ("sin_oferta", {"producto_id": "PROD-003", "cantidad": 100,
                         "presupuesto_centavos": 1200000, "plazo_max_dias": 7},
         {"estado": "sin_oferta"}),
    ]
    dataset = uuid4()
    ahora = datetime.now(timezone.utc)
    ejemplos = [Example(id=uuid4(), dataset_id=dataset, inputs={"solicitud": entrada},
                        outputs=esperado, created_at=ahora, metadata={"grupo": grupo})
                for grupo, entrada, esperado in casos]
    filas = list(evaluate(objetivo, data=ejemplos, evaluators=[evaluador],
                          upload_results=False, experiment_prefix="pedro-asistente-de-compras-componentes"))
    registro = [{"grupo": fila["example"].metadata["grupo"],
                 "salida": fila["run"].outputs,
                 "esperado": fila["example"].outputs,
                 "score": fila["evaluation_results"]["results"][0].score}
                for fila in filas]
    destino = Path("storage/evals/componentes.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"fecha_utc": ahora.isoformat(), "tipo": "componente_offline",
                                   "subido_langsmith": False, "casos": registro}, indent=2),
                       encoding="utf-8")
    print(f"{sum(c['score'] for c in registro)}/{len(registro)} casos correctos; {destino}")


if __name__ == "__main__":
    main()
