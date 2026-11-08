"""Índice FAISS y embeddings multilingües locales para piezas ficticias."""
import hashlib
import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
from fastembed import TextEmbedding

from .data import Catalogo, PIEZAS_DB, conectar, listar_productos
from .schemas import Producto

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_CACHE_DIR = Path("storage/models")
INDEX_DIR = Path("storage/indices/piezas")
INDEX_VERSION = 2


class IndiceNoDisponible(RuntimeError):
    pass


class EmbeddingsLocales:
    """Adaptador compatible con la indexación y consulta actuales."""

    def __init__(self) -> None:
        self.model = TextEmbedding(model_name=MODEL, cache_dir=str(MODEL_CACHE_DIR))

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        return list(self.model.embed(texts))

    def embed_query(self, text: str) -> np.ndarray:
        return next(iter(self.model.embed([text])))


@lru_cache(maxsize=1)
def embeddings_locales() -> EmbeddingsLocales:
    """Keep the ONNX model loaded across local searches."""
    return EmbeddingsLocales()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _documentos(db_path: Path) -> tuple[list[str], list[str]]:
    with conectar(db_path) as db:
        rows = db.execute("""
            SELECT p.sku, p.name, p.description, p.family, p.part_kind,
                   p.manufacturer, p.material, p.technical_specs_json,
                   c.name AS category
            FROM parts p JOIN categories c ON c.id=p.category_id ORDER BY p.id
        """).fetchall()
    skus = [row["sku"] for row in rows]
    texts = [". ".join((
        row["name"], f"Categoría: {row['category']}",
        f"Familia: {row['family']}", f"Tipo: {row['part_kind']}",
        f"Fabricante: {row['manufacturer']}", f"Material: {row['material']}",
        row["description"], "Especificaciones: " + ", ".join(
            f"{key}: {value}" for key, value in
            sorted(json.loads(row["technical_specs_json"]).items()))
    )) for row in rows]
    return skus, texts


def indexar_piezas(embeddings, *, db_path: Path = PIEZAS_DB,
                   index_dir: Path = INDEX_DIR) -> int:
    """Embed all source parts once and publish a checked, pickle-free index."""
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    source_hash = _sha256(db_path)
    skus, texts = _documentos(db_path)
    if not texts:
        raise ValueError("la base de piezas está vacía")
    vectors = np.asarray(embeddings.embed_documents(texts), dtype="float32")
    if (vectors.ndim != 2 or vectors.shape[0] != len(skus) or
            vectors.shape[1] < 1 or not np.isfinite(vectors).all()):
        raise ValueError("embeddings de piezas inválidos")
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    index_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=index_dir, suffix=".faiss", delete=False) as file:
        temp_index = Path(file.name)
    temp_manifest = None
    try:
        faiss.write_index(index, str(temp_index))
        manifest = {
            "version": INDEX_VERSION, "model": MODEL,
            "source_sha256": source_hash, "index_sha256": _sha256(temp_index),
            "dimension": index.d, "skus": skus,
        }
        with tempfile.NamedTemporaryFile(dir=index_dir, suffix=".json", mode="w",
                                         encoding="utf-8", delete=False) as file:
            temp_manifest = Path(file.name)
            json.dump(manifest, file, ensure_ascii=False)
        os.replace(temp_index, index_dir / "index.faiss")
        os.replace(temp_manifest, index_dir / "manifest.json")
    finally:
        temp_index.unlink(missing_ok=True)
        if temp_manifest is not None:
            temp_manifest.unlink(missing_ok=True)
    return len(skus)


def indice_disponible(index_dir: Path = INDEX_DIR) -> bool:
    return (index_dir / "index.faiss").is_file() and (index_dir / "manifest.json").is_file()


def buscar_piezas_semanticas(catalogo: Catalogo, texto: str, embeddings, *,
                             index_dir: Path = INDEX_DIR, db_path: Path = PIEZAS_DB,
                             limite: int = 10) -> list[Producto]:
    """Rank only SKUs in the active scenario; similarity never proves compatibility."""
    if not indice_disponible(index_dir):
        raise IndiceNoDisponible("índice de piezas ausente")
    meta = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    index_path = index_dir / "index.faiss"
    if (meta.get("version") != INDEX_VERSION or meta.get("model") != MODEL or
            meta.get("source_sha256") != _sha256(db_path) or
            meta.get("index_sha256") != _sha256(index_path)):
        raise IndiceNoDisponible("índice de piezas desactualizado o alterado")
    index = faiss.read_index(str(index_path))
    skus = meta.get("skus", [])
    if index.ntotal != len(skus) or index.d != meta.get("dimension"):
        raise IndiceNoDisponible("índice de piezas inconsistente")
    query = np.asarray([embeddings.embed_query(texto)], dtype="float32")
    if query.shape != (1, index.d) or not np.isfinite(query).all():
        raise ValueError("embedding de consulta inválido")
    faiss.normalize_L2(query)
    _, positions = index.search(query, index.ntotal)
    active = {product.modelo: product for product in listar_productos(catalogo)}
    return [active[skus[position]] for position in positions[0]
            if position >= 0 and skus[position] in active][:max(1, min(limite, 50))]
