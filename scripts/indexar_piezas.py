"""Genera el índice FAISS de piezas con un modelo multilingüe local."""
from compraslab.semantic_parts import INDEX_DIR, embeddings_locales, indexar_piezas


def main() -> None:
    count = indexar_piezas(embeddings_locales())
    print(f"Índice generado: {count} piezas en {INDEX_DIR}")


if __name__ == "__main__":
    main()
