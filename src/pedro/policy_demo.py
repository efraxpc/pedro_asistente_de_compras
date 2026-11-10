"""Corpus ficticio de T15: fragmentos trazables e índice FAISS en memoria."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from .memory import MODELO_RECUERDOS

if TYPE_CHECKING:
    from langchain_community.vectorstores import FAISS

CORPUS = Path(__file__).resolve().parents[2] / "knowledge/politicas_demo"
POLITICAS = {
    "devoluciones": ("devoluciones.md", "FIC-DEV-01"),
    "garantia": ("garantia.md", "FIC-GAR-01"),
    "entrega": ("entrega.md", "FIC-ENT-01"),
}
ORIGEN = "ficticio_demo"
TAMANO_FRAGMENTO = 700
SOLAPAMIENTO = 100
PREGUNTA_T24_ORIGINAL = "¿Se puede mandar en varias cajas?"
PREGUNTA_T24_REESCRITA = (
    "¿Cuándo admite la política de entrega un envío parcial de las piezas solicitadas?"
)
FRAGMENTO_T24_ESPERADO = "FIC-ENT-01-S05-C01"


def reescribir_consulta_entrega(pregunta: str) -> str | None:
    """Aclara preguntas coloquiales sobre dividir un envío, sin añadir la respuesta."""
    texto = pregunta.casefold()
    if re.search(r"\b(devoluci[oó]n|devolver|retornar)\b", texto):
        return None
    paquetes = re.search(r"\b(cajas?|paquetes?|bultos?|env[ií]os?)\b", texto)
    division = re.search(r"\b(varias?|m[uú]ltiples?|dos|separad[oa]s?|distint[oa]s?|parcial(?:es)?)\b",
                         texto)
    entrega = re.search(r"\b(mandar|enviar|despachar|entregar|llegar|pedido|entrega)\b", texto)
    return PREGUNTA_T24_REESCRITA if paquetes and division and entrega else None


def huella_corpus(carpeta: Path = CORPUS) -> str:
    """Identifica los textos usados para invalidar la caché de la interfaz."""
    digest = hashlib.sha256()
    for nombre, _ in POLITICAS.values():
        digest.update(nombre.encode("utf-8"))
        digest.update((carpeta / nombre).read_bytes())
    return digest.hexdigest()


def fragmentos_demo(carpeta: Path = CORPUS) -> list[Document]:
    """Divide cada sección sin perder tema, sección ni fuente de origen."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=TAMANO_FRAGMENTO,
        chunk_overlap=SOLAPAMIENTO,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    documentos = []
    for tema, (nombre, identificador) in POLITICAS.items():
        texto = (carpeta / nombre).read_text(encoding="utf-8")
        if "DEMOSTRACIÓN T15" not in texto or "corpus sintético" not in texto:
            raise ValueError(f"falta etiqueta ficticia en {nombre}")
        coincidencia_version = re.search(r"^\*\*Versión:\*\*\s*([^\s]+)", texto, flags=re.M)
        if coincidencia_version is None:
            raise ValueError(f"falta versión en {nombre}")
        version = coincidencia_version.group(1)
        secciones = [s.strip() for s in re.split(r"(?=^## )", texto, flags=re.M) if s.strip()]
        for numero_seccion, seccion in enumerate(secciones):
            titulo = seccion.splitlines()[0].removeprefix("## ").removeprefix("# ")
            for numero_fragmento, contenido in enumerate(splitter.split_text(seccion)):
                fuente_id = f"{identificador}-S{numero_seccion:02d}-C{numero_fragmento:02d}"
                documentos.append(Document(
                    id=fuente_id,
                    page_content=contenido,
                    metadata={"id": fuente_id, "origen": ORIGEN, "tema": tema,
                              "seccion": titulo, "fuente": nombre, "version": version},
                ))
    return documentos


def crear_indice_demo(carpeta: Path = CORPUS,
                      embeddings: Embeddings | None = None) -> FAISS:
    """Construye FAISS sin serializar ni cargar un docstore pickle."""
    from langchain_community.vectorstores import FAISS

    if embeddings is None:
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

        embeddings = FastEmbedEmbeddings(model_name=MODELO_RECUERDOS,
                                         doc_embed_type="passage")
    documentos = fragmentos_demo(carpeta)
    return FAISS.from_texts(
        [documento.page_content for documento in documentos],
        embeddings,
        metadatas=[documento.metadata for documento in documentos],
        ids=[documento.id for documento in documentos],
    )
