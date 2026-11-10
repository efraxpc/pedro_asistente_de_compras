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
    modelo = getattr(embeddings, "model_name", None) or getattr(embeddings, "model", None)
    if modelo != meta["embedding_model"]:
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


def consultar(indice, pregunta: str, k: int = 4, *,
             filtro: dict[str, str] | None = None, fetch_k: int = 20) -> list[dict]:
    """Recupera fragmentos y sus fuentes; el filtro se aplica a metadatos."""
    if indice is None:
        return []
    resultado = []
    encontrados = indice.similarity_search_with_score(
        pregunta, k=k, filter=filtro, fetch_k=max(fetch_k, k))
    for i, (doc, score) in enumerate(encontrados, 1):
        doc_id = getattr(doc, "id", None) or doc.metadata.get("id")
        if not doc_id:
            coincidencias = [x for x in indice.index_to_docstore_id.values()
                             if (candidato := indice.docstore.search(x)) == doc]
            doc_id = coincidencias[0] if len(coincidencias) == 1 else None
        resultado.append({"posicion": i, "fuente_id": doc_id, "texto": doc.page_content,
                          "metadatos": doc.metadata, "score": float(score)})
    return resultado


def diagnosticar_reescritura(indice, pregunta_original: str, pregunta_reescrita: str,
                             fuente_esperada: str, *, k: int = 4,
                             filtro: dict[str, str] | None = None,
                             fetch_k: int = 20) -> dict:
    """Compara dos consultas sobre el mismo índice, filtro y top-k."""
    import faiss
    from langchain_core.documents import Document

    if indice is None or k < 1 or fetch_k < 1:
        raise ValueError("índice y límites de búsqueda válidos requeridos")
    if not pregunta_original.strip() or not pregunta_reescrita.strip():
        raise ValueError("ambas preguntas son obligatorias")
    if pregunta_original == pregunta_reescrita:
        raise ValueError("la pregunta reescrita debe ser diferente")
    if fuente_esperada not in indice.index_to_docstore_id.values():
        raise ValueError("el fragmento esperado no existe en el índice")
    documento = indice.docstore.search(fuente_esperada)
    if not isinstance(documento, Document):
        raise ValueError("el fragmento esperado no existe en el docstore")
    tipos = {faiss.METRIC_L2: ("L2", "distancia_l2"),
             faiss.METRIC_INNER_PRODUCT: ("IP", "producto_interno")}
    if indice.index.metric_type not in tipos:
        raise ValueError("métrica FAISS no admitida para el diagnóstico")
    metrica, tipo_score = tipos[indice.index.metric_type]
    fetch_k = max(fetch_k, k)
    antes = consultar(indice, pregunta_original, k=k, filtro=filtro, fetch_k=fetch_k)
    despues = consultar(indice, pregunta_reescrita, k=k, filtro=filtro, fetch_k=fetch_k)

    def posicion(resultados: list[dict]) -> int | None:
        return next((r["posicion"] for r in resultados
                     if r["fuente_id"] == fuente_esperada), None)

    posicion_antes = posicion(antes)
    posicion_despues = posicion(despues)
    return {
        "pregunta_original": pregunta_original,
        "pregunta_reescrita": pregunta_reescrita,
        "fuente_esperada": fuente_esperada,
        "evidencia_esperada": {"texto": documento.page_content,
                               "metadatos": documento.metadata},
        "metrica": metrica,
        "tipo_score": tipo_score,
        "k": k,
        "fetch_k": fetch_k,
        "filtro": filtro,
        "total_fragmentos": indice.index.ntotal,
        "antes": antes,
        "despues": despues,
        "posicion_antes": posicion_antes,
        "posicion_despues": posicion_despues,
        "correccion_observada": posicion_antes is None and posicion_despues is not None,
    }
