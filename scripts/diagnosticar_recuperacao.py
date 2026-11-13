"""Reproduz uma falha de recuperação e mede o efeito de reescrever a consulta."""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from pedro.memory import MODELO_LEMBRANCAS
from pedro.policy_demo import (FRAGMENTO_T24_ESPERADO, PERGUNTA_T24_ORIGINAL,
                               PERGUNTA_T24_REESCRITA, criar_indice_demo,
                               impressao_corpus)
from pedro.rag import (carregar_indice, consultar, diagnosticar_reescrita,
                       inspecionar_indice)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indice", type=Path, help="pasta de um índice preexistente")
    parser.add_argument("--confiar-indice", action="store_true",
                        help="habilita o carregamento do docstore pickle após revisar a procedência")
    parser.add_argument("--embedder", choices=("auto", "openai", "fastembed"), default="auto")
    parser.add_argument("--original", help="pergunta que falha")
    parser.add_argument("--reescrita", help="pergunta reformulada")
    parser.add_argument("--fonte-esperada", help="ID do fragmento que contém a resposta")
    parser.add_argument("--filtro-tema", help="mesmo valor de tema para as duas buscas")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--fetch-k", type=int, default=20)
    parser.add_argument("--saida", type=Path, help="salva o relatório JSON")
    args = parser.parse_args()

    if args.indice is None:
        indice = criar_indice_demo()
        original = args.original or PERGUNTA_T24_ORIGINAL
        reescrita = args.reescrita or PERGUNTA_T24_REESCRITA
        fonte = args.fonte_esperada or FRAGMENTO_T24_ESPERADO
        procedencia = {"tipo": "demo_ficticia_em_memoria",
                       "corpus_sha256": impressao_corpus(),
                       "embedding_model": MODELO_LEMBRANCAS}
    else:
        if not args.confiar_indice:
            parser.error("revise a origem e o manifesto antes de usar --confiar-indice")
        if not all((args.original, args.reescrita, args.fonte_esperada)):
            parser.error("--indice requer --original, --reescrita e --fonte-esperada")
        meta = inspecionar_indice(args.indice)
        modelo = meta["embedding_model"]
        tipo = args.embedder
        if tipo == "auto":
            tipo = "fastembed" if modelo == MODELO_LEMBRANCAS else "openai"
        if tipo == "fastembed":
            from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
            embeddings = FastEmbedEmbeddings(model_name=modelo, doc_embed_type="passage")
        else:
            from langchain_openai import OpenAIEmbeddings
            load_dotenv()
            embeddings = OpenAIEmbeddings(model=modelo)
        indice, _ = carregar_indice(args.indice, embeddings, origem_confiavel=True)
        original, reescrita, fonte = args.original, args.reescrita, args.fonte_esperada
        procedencia = {"tipo": "indice_preexistente", "origem": meta["origem"],
                       "embedding_model": modelo, "sha256": meta["sha256"]}

    filtro = {"tema": args.filtro_tema} if args.filtro_tema else None
    relatorio = diagnosticar_reescrita(
        indice, original, reescrita, fonte, k=args.k,
        filtro=filtro, fetch_k=args.fetch_k)
    relatorio["procedencia"] = procedencia
    if args.indice is None and filtro is None:
        relatorio["teste_filtro_tema"] = consultar(
            indice, original, k=args.k, filtro={"tema": "entrega"},
            fetch_k=indice.index.ntotal)

    conteudo = json.dumps(relatorio, ensure_ascii=False, indent=2)
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(conteudo + "\n", encoding="utf-8")
    print(conteudo)
    return 0 if relatorio["correcao_observada"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
