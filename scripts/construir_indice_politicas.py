"""Construye una vez el índice FAISS de políticas y lo guarda en knowledge/politicas/.

Es el paso de indexación, separado del agente: el agente y la app solo cargan el índice
ya guardado. El corpus es ficticio (knowledge/politicas_demo). No requiere credenciales.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pedro.memory import MODELO_RECUERDOS
from pedro.policy_demo import (CORPUS, ORIGEN, SOLAPAMIENTO, TAMANO_FRAGMENTO,
                               crear_indice_demo, huella_corpus)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--destino", type=Path, default=ROOT / "knowledge/politicas")
    destino = argumentos.parse_args().destino
    import faiss

    indice = crear_indice_demo()
    destino.mkdir(parents=True, exist_ok=True)
    indice.save_local(str(destino))
    documentos = [{"id": doc_id, "metadata": getattr(indice.docstore.search(doc_id), "metadata")}
                  for doc_id in indice.index_to_docstore_id.values()]
    manifiesto = {
        "origen": f"{ORIGEN}: corpus propio en {CORPUS.relative_to(ROOT)}, "
                  "indexado por scripts/construir_indice_politicas.py",
        "embedding_model": MODELO_RECUERDOS,
        "dimension": indice.index.d,
        "metrica": "L2" if indice.index.metric_type == faiss.METRIC_L2 else "IP",
        "documentos": documentos,
        "sha256": {nombre: hashlib.sha256((destino / nombre).read_bytes()).hexdigest()
                   for nombre in ("index.faiss", "index.pkl")},
        "corpus_sha256": huella_corpus(),
        "fragmentacion": {"tamano": TAMANO_FRAGMENTO, "solapamiento": SOLAPAMIENTO},
        "creado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (destino / "manifest.json").write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"índice guardado en {destino}: {indice.index.ntotal} fragmentos, "
          f"dimensión {indice.index.d}, métrica {manifiesto['metrica']}")


if __name__ == "__main__":
    main()
