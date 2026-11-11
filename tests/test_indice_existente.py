"""O índice salvo em knowledge/politicas/ deve poder ser carregado e continuar em dia."""
import shutil
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from pedro.memory import MODELO_LEMBRANCAS
from pedro.policy_demo import FRAGMENTO_T24_ESPERADO, fragmentos_demo, impressao_corpus
from pedro.rag import carregar_indice, inspecionar_indice

PASTA = Path(__file__).resolve().parents[1] / "knowledge/politicas"


class EmbeddingsDeclarados(Embeddings):
    """Só declara o modelo: carregar o índice não calcula nenhum embedding."""
    model_name = MODELO_LEMBRANCAS

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("carregar o índice não deve indexar documentos")

    def embed_query(self, text: str) -> list[float]:
        raise AssertionError("este teste não consulta o índice")


def test_o_indice_salvo_e_carregado_sem_reconstrui_lo():
    manifesto = inspecionar_indice(PASTA)
    indice, _ = carregar_indice(PASTA, EmbeddingsDeclarados(), origem_confiavel=True)
    originais = {d.metadata["id"]: d.page_content for d in fragmentos_demo()}
    assert indice.index.ntotal == len(manifesto["documentos"]) == len(originais)
    assert indice.docstore.search(FRAGMENTO_T24_ESPERADO).page_content == originais[
        FRAGMENTO_T24_ESPERADO]


def test_o_indice_salvo_corresponde_ao_corpus_atual():
    assert inspecionar_indice(PASTA)["corpus_sha256"] == impressao_corpus(), (
        "o corpus mudou: execute scripts/construir_indice_politicas.py")


def test_a_porta_rejeita_carga_sem_confianca_e_arquivos_alterados(tmp_path):
    with pytest.raises(PermissionError):
        carregar_indice(PASTA, EmbeddingsDeclarados(), origem_confiavel=False)
    copia = tmp_path / "politicas"
    shutil.copytree(PASTA, copia)
    with (copia / "index.pkl").open("ab") as arquivo:
        arquivo.write(b"alterado")
    with pytest.raises(ValueError, match="impressão digital incorreta"):
        carregar_indice(copia, EmbeddingsDeclarados(), origem_confiavel=True)
