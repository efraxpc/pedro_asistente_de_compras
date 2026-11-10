"""El índice guardado en knowledge/politicas/ debe poder cargarse y seguir al día."""
import shutil
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from pedro.memory import MODELO_RECUERDOS
from pedro.policy_demo import FRAGMENTO_T24_ESPERADO, fragmentos_demo, huella_corpus
from pedro.rag import cargar_indice, inspeccionar_indice

CARPETA = Path(__file__).resolve().parents[1] / "knowledge/politicas"


class EmbeddingsDeclarados(Embeddings):
    """Solo declara el modelo: cargar el índice no calcula ningún embedding."""
    model_name = MODELO_RECUERDOS

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("cargar el índice no debe indexar documentos")

    def embed_query(self, text: str) -> list[float]:
        raise AssertionError("esta prueba no consulta el índice")


def test_el_indice_guardado_se_carga_sin_reconstruirlo():
    manifiesto = inspeccionar_indice(CARPETA)
    indice, _ = cargar_indice(CARPETA, EmbeddingsDeclarados(), origen_confiable=True)
    originales = {d.metadata["id"]: d.page_content for d in fragmentos_demo()}
    assert indice.index.ntotal == len(manifiesto["documentos"]) == len(originales)
    assert indice.docstore.search(FRAGMENTO_T24_ESPERADO).page_content == originales[
        FRAGMENTO_T24_ESPERADO]


def test_el_indice_guardado_corresponde_al_corpus_actual():
    assert inspeccionar_indice(CARPETA)["corpus_sha256"] == huella_corpus(), (
        "el corpus cambió: ejecute scripts/construir_indice_politicas.py")


def test_la_puerta_rechaza_carga_sin_confianza_y_archivos_alterados(tmp_path):
    with pytest.raises(PermissionError):
        cargar_indice(CARPETA, EmbeddingsDeclarados(), origen_confiable=False)
    copia = tmp_path / "politicas"
    shutil.copytree(CARPETA, copia)
    with (copia / "index.pkl").open("ab") as archivo:
        archivo.write(b"alterado")
    with pytest.raises(ValueError, match="huella incorrecta"):
        cargar_indice(copia, EmbeddingsDeclarados(), origen_confiable=True)
