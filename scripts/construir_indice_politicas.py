"""Constrói uma vez o índice FAISS de políticas e o salva em knowledge/politicas/.

É o passo de indexação, separado do agente: o agente e o app só carregam o índice
já salvo. O corpus é fictício (knowledge/politicas_demo). Não requer credenciais.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pedro.memory import MODELO_LEMBRANCAS
from pedro.policy_demo import (CORPUS, ORIGEM, SOBREPOSICAO, TAMANHO_FRAGMENTO,
                               criar_indice_demo, impressao_corpus)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--destino", type=Path, default=ROOT / "knowledge/politicas")
    destino = argumentos.parse_args().destino
    import faiss

    indice = criar_indice_demo()
    destino.mkdir(parents=True, exist_ok=True)
    indice.save_local(str(destino))
    documentos = [{"id": doc_id, "metadata": getattr(indice.docstore.search(doc_id), "metadata")}
                  for doc_id in indice.index_to_docstore_id.values()]
    manifesto = {
        "origem": f"{ORIGEM}: corpus próprio em {CORPUS.relative_to(ROOT)}, "
                  "indexado por scripts/construir_indice_politicas.py",
        "embedding_model": MODELO_LEMBRANCAS,
        "dimension": indice.index.d,
        "metrica": "L2" if indice.index.metric_type == faiss.METRIC_L2 else "IP",
        "documentos": documentos,
        "sha256": {nome: hashlib.sha256((destino / nome).read_bytes()).hexdigest()
                   for nome in ("index.faiss", "index.pkl")},
        "corpus_sha256": impressao_corpus(),
        "fragmentacao": {"tamanho": TAMANHO_FRAGMENTO, "sobreposicao": SOBREPOSICAO},
        "criado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (destino / "manifest.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"índice salvo em {destino}: {indice.index.ntotal} fragmentos, "
          f"dimensão {indice.index.d}, métrica {manifesto['metrica']}")


if __name__ == "__main__":
    main()
