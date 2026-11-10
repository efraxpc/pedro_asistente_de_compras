"""Reproduce un fallo de recuperación y mide el efecto de reescribir la consulta."""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from pedro.memory import MODELO_RECUERDOS
from pedro.policy_demo import (FRAGMENTO_T24_ESPERADO, PREGUNTA_T24_ORIGINAL,
                               PREGUNTA_T24_REESCRITA, crear_indice_demo,
                               huella_corpus)
from pedro.rag import (cargar_indice, consultar, diagnosticar_reescritura,
                       inspeccionar_indice)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indice", type=Path, help="carpeta de un índice preexistente")
    parser.add_argument("--confiar-indice", action="store_true",
                        help="habilita la carga del docstore pickle tras revisar su procedencia")
    parser.add_argument("--embedder", choices=("auto", "openai", "fastembed"), default="auto")
    parser.add_argument("--original", help="pregunta que falla")
    parser.add_argument("--reescrita", help="pregunta reformulada")
    parser.add_argument("--fuente-esperada", help="ID del fragmento que contiene la respuesta")
    parser.add_argument("--filtro-tema", help="mismo valor de tema para ambas búsquedas")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--fetch-k", type=int, default=20)
    parser.add_argument("--salida", type=Path, help="guarda el informe JSON")
    args = parser.parse_args()

    if args.indice is None:
        indice = crear_indice_demo()
        original = args.original or PREGUNTA_T24_ORIGINAL
        reescrita = args.reescrita or PREGUNTA_T24_REESCRITA
        fuente = args.fuente_esperada or FRAGMENTO_T24_ESPERADO
        procedencia = {"tipo": "demo_ficticia_en_memoria",
                       "corpus_sha256": huella_corpus(),
                       "embedding_model": MODELO_RECUERDOS}
    else:
        if not args.confiar_indice:
            parser.error("revise el origen y el manifiesto antes de usar --confiar-indice")
        if not all((args.original, args.reescrita, args.fuente_esperada)):
            parser.error("--indice requiere --original, --reescrita y --fuente-esperada")
        meta = inspeccionar_indice(args.indice)
        modelo = meta["embedding_model"]
        tipo = args.embedder
        if tipo == "auto":
            tipo = "fastembed" if modelo == MODELO_RECUERDOS else "openai"
        if tipo == "fastembed":
            from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
            embeddings = FastEmbedEmbeddings(model_name=modelo, doc_embed_type="passage")
        else:
            from langchain_openai import OpenAIEmbeddings
            load_dotenv()
            embeddings = OpenAIEmbeddings(model=modelo)
        indice, _ = cargar_indice(args.indice, embeddings, origen_confiable=True)
        original, reescrita, fuente = args.original, args.reescrita, args.fuente_esperada
        procedencia = {"tipo": "indice_preexistente", "origen": meta["origen"],
                       "embedding_model": modelo, "sha256": meta["sha256"]}

    filtro = {"tema": args.filtro_tema} if args.filtro_tema else None
    informe = diagnosticar_reescritura(
        indice, original, reescrita, fuente, k=args.k,
        filtro=filtro, fetch_k=args.fetch_k)
    informe["procedencia"] = procedencia
    if args.indice is None and filtro is None:
        informe["prueba_filtro_tema"] = consultar(
            indice, original, k=args.k, filtro={"tema": "entrega"},
            fetch_k=indice.index.ntotal)

    contenido = json.dumps(informe, ensure_ascii=False, indent=2)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(contenido + "\n", encoding="utf-8")
    print(contenido)
    return 0 if informe["correccion_observada"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
