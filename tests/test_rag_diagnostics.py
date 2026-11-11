import hashlib
import json

import pytest
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from pedro.agent import criar_fluxo
from pedro.catalog import criar_cenario
from pedro.memory import nova_sessao
from pedro.policy_demo import criar_indice_demo
from pedro.rag import carregar_indice, diagnosticar_reescrita


class EmbeddingsTeste(Embeddings):
    model_name = "embeddings-teste"
    model = object()  # O FastEmbed também expõe um objeto aqui, não o nome.

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(texto) for texto in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0] if "caixas" in text else [0.0, 1.0]


def _indice_teste():
    return FAISS.from_texts(
        ["caixas de embalagem"] * 4 + ["entrega parcial de peças"],
        EmbeddingsTeste(),
        metadatas=[{"tema": "entrega", "fonte": "teste.md"}] * 5,
        ids=[f"caixa-{i}" for i in range(4)] + ["entrega-parcial"],
    )


def test_diagnostico_exige_evidencia_no_corpus_e_mede_reescrita():
    indice = _indice_teste()
    relatorio = diagnosticar_reescrita(
        indice, "Várias caixas?", "É permitida a entrega parcial?", "entrega-parcial",
        k=2, filtro={"tema": "entrega"}, fetch_k=5)

    assert relatorio["metrica"] == "L2"
    assert relatorio["tipo_score"] == "distancia_l2"
    assert relatorio["k"] == 2 and relatorio["filtro"] == {"tema": "entrega"}
    assert relatorio["posicao_antes"] is None
    assert relatorio["posicao_depois"] == 1
    assert relatorio["correcao_observada"] is True
    assert relatorio["evidencia_esperada"]["texto"] == "entrega parcial de peças"
    assert all(r["fonte_id"].startswith("caixa-") for r in relatorio["antes"])

    with pytest.raises(ValueError, match="não existe"):
        diagnosticar_reescrita(indice, "caixas", "entrega", "fonte-inventada")


def test_carregador_aceita_model_name_e_verifica_indice_salvo(tmp_path):
    indice = _indice_teste()
    indice.save_local(str(tmp_path))
    documentos = []
    for doc_id in indice.index_to_docstore_id.values():
        documento = indice.docstore.search(doc_id)
        documentos.append({"id": doc_id, "metadata": documento.metadata})
    meta = {
        "origem": "fixture_local_criada_no_teste",
        "embedding_model": EmbeddingsTeste.model_name,
        "dimension": 2,
        "metrica": "L2",
        "documentos": documentos,
        "sha256": {nome: hashlib.sha256((tmp_path / nome).read_bytes()).hexdigest()
                   for nome in ("index.faiss", "index.pkl")},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(meta), encoding="utf-8")

    carregado, manifesto = carregar_indice(tmp_path, EmbeddingsTeste(), origem_confiavel=True)
    assert manifesto["origem"] == "fixture_local_criada_no_teste"
    assert carregado.index.ntotal == 5
    assert carregado.docstore.search("entrega-parcial").page_content == "entrega parcial de peças"


def test_comando_t24_no_chat_mostra_falha_e_correcao_sem_llm(tmp_path):
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    fluxo = criar_fluxo(cenario, memoria, indice=criar_indice_demo())

    saida = fluxo.invoke({"input": "/t24"}, config={"configurable": {
        "user_id": "ana", "session_id": sessao}})

    assert "Teste T24 · recuperação fictícia" in saida.content
    assert "FIC-ENT-01-S05-C01" in saida.content
    assert "antes fora do top-4; depois 1" in saida.content
    assert "filtro `tema=entrega`" in saida.content
    assert "não posso confirmar uma recomendação" not in saida.content.lower()
