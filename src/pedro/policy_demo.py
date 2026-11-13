"""Corpus fictício de políticas: fragmentos rastreáveis e índice FAISS em memória."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from .memory import MODELO_LEMBRANCAS

if TYPE_CHECKING:
    from langchain_community.vectorstores import FAISS

CORPUS = Path(__file__).resolve().parents[2] / "knowledge/politicas_demo"
POLITICAS = {
    "devolucoes": ("devolucoes.md", "FIC-DEV-01"),
    "garantia": ("garantia.md", "FIC-GAR-01"),
    "entrega": ("entrega.md", "FIC-ENT-01"),
}
ORIGEM = "ficticio_demo"
TAMANHO_FRAGMENTO = 700
SOBREPOSICAO = 100
PERGUNTA_T24_ORIGINAL = "Posso receber em várias caixas?"
PERGUNTA_T24_REESCRITA = (
    "Quando a política de entrega admite um envio parcial das peças solicitadas?"
)
FRAGMENTO_T24_ESPERADO = "FIC-ENT-01-S05-C01"


def reescrever_consulta_entrega(pergunta: str) -> str | None:
    """Esclarece perguntas coloquiais sobre dividir um envio, sem acrescentar a resposta."""
    texto = pergunta.casefold()
    if re.search(r"\b(devolu[cç][aã]o|devolu[cç][oõ]es|devolver|retornar)\b", texto):
        return None
    pacotes = re.search(r"\b(caixas?|pacotes?|volumes?|envios?|remessas?)\b", texto)
    divisao = re.search(r"\b(v[aá]ri[oa]s|m[uú]ltipl[oa]s?|dois|duas|separad[oa]s?|diferentes?|"
                        r"distint[oa]s?|parcial|parciais)\b", texto)
    entrega = re.search(r"\b(mandar|enviar|despachar|entregar|receber|chegar|pedido|entrega)\b", texto)
    return PERGUNTA_T24_REESCRITA if pacotes and divisao and entrega else None


def impressao_corpus(pasta: Path = CORPUS) -> str:
    """Identifica os textos usados para invalidar o cache da interface."""
    digest = hashlib.sha256()
    for nome, _ in POLITICAS.values():
        digest.update(nome.encode("utf-8"))
        digest.update((pasta / nome).read_bytes())
    return digest.hexdigest()


def fragmentos_demo(pasta: Path = CORPUS) -> list[Document]:
    """Divide cada seção sem perder tema, seção nem fonte de origem."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=TAMANHO_FRAGMENTO,
        chunk_overlap=SOBREPOSICAO,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    documentos = []
    for tema, (nome, identificador) in POLITICAS.items():
        texto = (pasta / nome).read_text(encoding="utf-8")
        if "DEMONSTRAÇÃO" not in texto or "corpus sintético" not in texto:
            raise ValueError(f"falta o rótulo fictício em {nome}")
        coincidencia_versao = re.search(r"^\*\*Versão:\*\*\s*([^\s]+)", texto, flags=re.M)
        if coincidencia_versao is None:
            raise ValueError(f"falta a versão em {nome}")
        versao = coincidencia_versao.group(1)
        secoes = [s.strip() for s in re.split(r"(?=^## )", texto, flags=re.M) if s.strip()]
        for numero_secao, secao in enumerate(secoes):
            titulo = secao.splitlines()[0].removeprefix("## ").removeprefix("# ")
            for numero_fragmento, conteudo in enumerate(splitter.split_text(secao)):
                fonte_id = f"{identificador}-S{numero_secao:02d}-C{numero_fragmento:02d}"
                documentos.append(Document(
                    id=fonte_id,
                    page_content=conteudo,
                    metadata={"id": fonte_id, "origem": ORIGEM, "tema": tema,
                              "secao": titulo, "fonte": nome, "versao": versao},
                ))
    return documentos


def criar_indice_demo(pasta: Path = CORPUS,
                      embeddings: Embeddings | None = None) -> FAISS:
    """Constrói o FAISS sem serializar nem carregar um docstore pickle."""
    from langchain_community.vectorstores import FAISS

    if embeddings is None:
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

        embeddings = FastEmbedEmbeddings(model_name=MODELO_LEMBRANCAS,
                                         doc_embed_type="passage")
    documentos = fragmentos_demo(pasta)
    return FAISS.from_texts(
        [documento.page_content for documento in documentos],
        embeddings,
        metadatas=[documento.metadata for documento in documentos],
        ids=[documento.id for documento in documentos],
    )
