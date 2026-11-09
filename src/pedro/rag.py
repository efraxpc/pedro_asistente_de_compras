"""Carga de políticas condicionada a procedencia y hashes verificados."""
import hashlib
import json
from pathlib import Path


def inspeccionar_indice(carpeta: Path) -> dict:
    meta = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
    requeridos = {"origen", "embedding_model", "dimension", "metrica", "documentos", "sha256"}
    if (not requeridos.issubset(meta) or not meta["origen"] or
            not meta["embedding_model"] or meta["dimension"] < 1):
        raise ValueError("manifiesto incompleto")
    if (meta["metrica"] not in ("L2", "IP") or
            not isinstance(meta["documentos"], list) or
            any(not isinstance(d, dict) or not {"id", "metadata"}.issubset(d)
                for d in meta["documentos"])):
        raise ValueError("metadatos de índice inválidos")
    for nombre in ("index.faiss", "index.pkl"):
        archivo = carpeta / nombre
        if hashlib.sha256(archivo.read_bytes()).hexdigest() != meta["sha256"].get(nombre):
            raise ValueError(f"huella incorrecta: {nombre}")
    return meta


def cargar_indice(carpeta: Path, embeddings, *, origen_confiable: bool):
    meta = inspeccionar_indice(carpeta)
    if not origen_confiable:
        raise PermissionError("se requiere confianza explícita para deserializar index.pkl")
    if getattr(embeddings, "model", None) != meta["embedding_model"]:
        raise ValueError("modelo de embeddings distinto")
    from langchain_community.vectorstores import FAISS
    import faiss
    indice = FAISS.load_local(str(carpeta), embeddings, allow_dangerous_deserialization=True)
    if indice.index.d != meta["dimension"] or indice.index.ntotal != len(meta["documentos"]):
        raise ValueError("dimensión o recuento distinto")
    metrica = faiss.METRIC_L2 if meta["metrica"] == "L2" else faiss.METRIC_INNER_PRODUCT
    if indice.index.metric_type != metrica:
        raise ValueError("métrica distinta")
    documentos = {d["id"]: d["metadata"] for d in meta["documentos"]}
    if set(indice.index_to_docstore_id.values()) != set(documentos):
        raise ValueError("identificadores de documentos distintos")
    for doc_id, metadata in documentos.items():
        doc = indice.docstore.search(doc_id)
        if not hasattr(doc, "metadata") or doc.metadata != metadata:
            raise ValueError("metadatos de documentos distintos")
    return indice, meta


def consultar(indice, pregunta: str, k: int = 4) -> list[dict]:
    if indice is None:
        return []
    resultado = []
    for i, (doc, score) in enumerate(indice.similarity_search_with_score(pregunta, k=k), 1):
        doc_id = getattr(doc, "id", None) or doc.metadata.get("id")
        if not doc_id:
            coincidencias = [x for x in indice.index_to_docstore_id.values()
                             if (candidato := indice.docstore.search(x)) == doc]
            doc_id = coincidencias[0] if len(coincidencias) == 1 else None
        resultado.append({"posicion": i, "fuente_id": doc_id, "texto": doc.page_content,
                          "metadatos": doc.metadata, "score": score})
    return resultado
