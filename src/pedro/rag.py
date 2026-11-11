"""Carga de políticas condicionada a procedência e hashes verificados."""
import hashlib
import json
from pathlib import Path


def inspecionar_indice(pasta: Path) -> dict:
    meta = json.loads((pasta / "manifest.json").read_text(encoding="utf-8"))
    requeridos = {"origem", "embedding_model", "dimension", "metrica", "documentos", "sha256"}
    if (not requeridos.issubset(meta) or not meta["origem"] or
            not meta["embedding_model"] or meta["dimension"] < 1):
        raise ValueError("manifesto incompleto")
    if (meta["metrica"] not in ("L2", "IP") or
            not isinstance(meta["documentos"], list) or
            any(not isinstance(d, dict) or not {"id", "metadata"}.issubset(d)
                for d in meta["documentos"])):
        raise ValueError("metadados de índice inválidos")
    for nome in ("index.faiss", "index.pkl"):
        arquivo = pasta / nome
        if hashlib.sha256(arquivo.read_bytes()).hexdigest() != meta["sha256"].get(nome):
            raise ValueError(f"impressão digital incorreta: {nome}")
    return meta


def carregar_indice(pasta: Path, embeddings, *, origem_confiavel: bool):
    meta = inspecionar_indice(pasta)
    if not origem_confiavel:
        raise PermissionError("é necessária confiança explícita para desserializar index.pkl")
    modelo = getattr(embeddings, "model_name", None) or getattr(embeddings, "model", None)
    if modelo != meta["embedding_model"]:
        raise ValueError("modelo de embeddings diferente")
    from langchain_community.vectorstores import FAISS
    import faiss
    indice = FAISS.load_local(str(pasta), embeddings, allow_dangerous_deserialization=True)
    if indice.index.d != meta["dimension"] or indice.index.ntotal != len(meta["documentos"]):
        raise ValueError("dimensão ou contagem diferente")
    metrica = faiss.METRIC_L2 if meta["metrica"] == "L2" else faiss.METRIC_INNER_PRODUCT
    if indice.index.metric_type != metrica:
        raise ValueError("métrica diferente")
    documentos = {d["id"]: d["metadata"] for d in meta["documentos"]}
    if set(indice.index_to_docstore_id.values()) != set(documentos):
        raise ValueError("identificadores de documentos diferentes")
    for doc_id, metadata in documentos.items():
        doc = indice.docstore.search(doc_id)
        if not hasattr(doc, "metadata") or doc.metadata != metadata:
            raise ValueError("metadados de documentos diferentes")
    return indice, meta


def consultar(indice, pergunta: str, k: int = 4, *,
              filtro: dict[str, str] | None = None, fetch_k: int = 20) -> list[dict]:
    """Recupera fragmentos e suas fontes; o filtro é aplicado aos metadados."""
    if indice is None:
        return []
    resultado = []
    encontrados = indice.similarity_search_with_score(
        pergunta, k=k, filter=filtro, fetch_k=max(fetch_k, k))
    for i, (doc, score) in enumerate(encontrados, 1):
        doc_id = getattr(doc, "id", None) or doc.metadata.get("id")
        if not doc_id:
            coincidencias = [x for x in indice.index_to_docstore_id.values()
                             if indice.docstore.search(x) == doc]
            doc_id = coincidencias[0] if len(coincidencias) == 1 else None
        resultado.append({"posicao": i, "fonte_id": doc_id, "texto": doc.page_content,
                          "metadados": doc.metadata, "score": float(score)})
    return resultado


def diagnosticar_reescrita(indice, pergunta_original: str, pergunta_reescrita: str,
                           fonte_esperada: str, *, k: int = 4,
                           filtro: dict[str, str] | None = None,
                           fetch_k: int = 20) -> dict:
    """Compara duas consultas sobre o mesmo índice, filtro e top-k."""
    import faiss
    from langchain_core.documents import Document

    if indice is None or k < 1 or fetch_k < 1:
        raise ValueError("índice e limites de busca válidos são obrigatórios")
    if not pergunta_original.strip() or not pergunta_reescrita.strip():
        raise ValueError("as duas perguntas são obrigatórias")
    if pergunta_original == pergunta_reescrita:
        raise ValueError("a pergunta reescrita deve ser diferente")
    if fonte_esperada not in indice.index_to_docstore_id.values():
        raise ValueError("o fragmento esperado não existe no índice")
    documento = indice.docstore.search(fonte_esperada)
    if not isinstance(documento, Document):
        raise ValueError("o fragmento esperado não existe no docstore")
    tipos = {faiss.METRIC_L2: ("L2", "distancia_l2"),
             faiss.METRIC_INNER_PRODUCT: ("IP", "produto_interno")}
    if indice.index.metric_type not in tipos:
        raise ValueError("métrica FAISS não suportada para o diagnóstico")
    metrica, tipo_score = tipos[indice.index.metric_type]
    fetch_k = max(fetch_k, k)
    antes = consultar(indice, pergunta_original, k=k, filtro=filtro, fetch_k=fetch_k)
    depois = consultar(indice, pergunta_reescrita, k=k, filtro=filtro, fetch_k=fetch_k)

    def posicao(resultados: list[dict]) -> int | None:
        return next((r["posicao"] for r in resultados
                     if r["fonte_id"] == fonte_esperada), None)

    posicao_antes = posicao(antes)
    posicao_depois = posicao(depois)
    return {
        "pergunta_original": pergunta_original,
        "pergunta_reescrita": pergunta_reescrita,
        "fonte_esperada": fonte_esperada,
        "evidencia_esperada": {"texto": documento.page_content,
                               "metadados": documento.metadata},
        "metrica": metrica,
        "tipo_score": tipo_score,
        "k": k,
        "fetch_k": fetch_k,
        "filtro": filtro,
        "total_fragmentos": indice.index.ntotal,
        "antes": antes,
        "depois": depois,
        "posicao_antes": posicao_antes,
        "posicao_depois": posicao_depois,
        "correcao_observada": posicao_antes is None and posicao_depois is not None,
    }
