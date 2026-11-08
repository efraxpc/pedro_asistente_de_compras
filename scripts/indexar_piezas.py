"""Genera el índice semántico de piezas con OPENAI_API_KEY (una sola vez por base)."""
import os

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

from compraslab.semantic_parts import INDEX_DIR, MODEL, indexar_piezas


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Configure OPENAI_API_KEY para generar el índice de piezas.")
    count = indexar_piezas(OpenAIEmbeddings(model=MODEL))
    print(f"Índice generado: {count} piezas en {INDEX_DIR}")


if __name__ == "__main__":
    main()
