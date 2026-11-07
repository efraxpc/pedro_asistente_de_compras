"""Carga de un índice de políticas recibido y documentado; nunca lo inventa."""
import json
from pathlib import Path


class IndiceAusente(RuntimeError):
    pass


def cargar_indice_politicas(carpeta: Path, embeddings, *, origen_confiable: bool = False):
    from langchain_community.vectorstores import FAISS

    manifiesto = carpeta / "manifest.json"
    if not manifiesto.is_file() or not (carpeta / "index.faiss").is_file():
        raise IndiceAusente("Falta índice FAISS preconstruido y su manifiesto de procedencia")
    meta = json.loads(manifiesto.read_text(encoding="utf-8"))
    for clave in ("embedding_model", "dimension", "origen", "documentos"):
        if clave not in meta:
            raise ValueError(f"manifiesto sin {clave}")
    if not (carpeta / "index.pkl").is_file():
        raise IndiceAusente("Falta docstore del índice")
    if not origen_confiable:
        raise ValueError("el docstore pickle requiere procedencia local verificada")
    # FAISS.load_local usa pickle: solo se permite una ruta local confiable.
    indice = FAISS.load_local(str(carpeta), embeddings, allow_dangerous_deserialization=True)
    if indice.index.d != meta["dimension"]:
        raise ValueError("dimensión de embeddings incompatible")
    if not indice.index_to_docstore_id:
        raise ValueError("índice sin IDs de documentos")
    for doc_id in indice.index_to_docstore_id.values():
        doc = indice.docstore.search(doc_id)
        if not hasattr(doc, "metadata") or not doc.metadata.get("id"):
            raise ValueError("documento sin ID de procedencia")
    return indice, meta
