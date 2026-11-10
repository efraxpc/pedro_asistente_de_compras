import hashlib
import json

import pytest
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from pedro.agent import crear_flujo
from pedro.catalog import crear_escenario
from pedro.memory import nueva_sesion
from pedro.policy_demo import crear_indice_demo
from pedro.rag import cargar_indice, diagnosticar_reescritura


class EmbeddingsPrueba(Embeddings):
    model_name = "embeddings-prueba"
    model = object()  # FastEmbed también expone un objeto aquí, no el nombre.

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(texto) for texto in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0] if "cajas" in text else [0.0, 1.0]


def _indice_prueba():
    return FAISS.from_texts(
        ["cajas de embalaje"] * 4 + ["entrega parcial de piezas"],
        EmbeddingsPrueba(),
        metadatas=[{"tema": "entrega", "fuente": "prueba.md"}] * 5,
        ids=[f"caja-{i}" for i in range(4)] + ["entrega-parcial"],
    )


def test_diagnostico_exige_evidencia_en_corpus_y_mide_reescritura():
    indice = _indice_prueba()
    informe = diagnosticar_reescritura(
        indice, "¿Varias cajas?", "¿Se permite entrega parcial?", "entrega-parcial",
        k=2, filtro={"tema": "entrega"}, fetch_k=5)

    assert informe["metrica"] == "L2"
    assert informe["tipo_score"] == "distancia_l2"
    assert informe["k"] == 2 and informe["filtro"] == {"tema": "entrega"}
    assert informe["posicion_antes"] is None
    assert informe["posicion_despues"] == 1
    assert informe["correccion_observada"] is True
    assert informe["evidencia_esperada"]["texto"] == "entrega parcial de piezas"
    assert all(r["fuente_id"].startswith("caja-") for r in informe["antes"])

    with pytest.raises(ValueError, match="no existe"):
        diagnosticar_reescritura(indice, "cajas", "entrega", "fuente-inventada")


def test_cargador_acepta_model_name_y_verifica_indice_guardado(tmp_path):
    indice = _indice_prueba()
    indice.save_local(str(tmp_path))
    documentos = []
    for doc_id in indice.index_to_docstore_id.values():
        documento = indice.docstore.search(doc_id)
        documentos.append({"id": doc_id, "metadata": documento.metadata})
    meta = {
        "origen": "fixture_local_creada_en_prueba",
        "embedding_model": EmbeddingsPrueba.model_name,
        "dimension": 2,
        "metrica": "L2",
        "documentos": documentos,
        "sha256": {nombre: hashlib.sha256((tmp_path / nombre).read_bytes()).hexdigest()
                   for nombre in ("index.faiss", "index.pkl")},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(meta), encoding="utf-8")

    cargado, manifiesto = cargar_indice(tmp_path, EmbeddingsPrueba(), origen_confiable=True)
    assert manifiesto["origen"] == "fixture_local_creada_en_prueba"
    assert cargado.index.ntotal == 5
    assert cargado.docstore.search("entrega-parcial").page_content == "entrega parcial de piezas"


def test_comando_t24_en_chat_muestra_fallo_y_correccion_sin_llm(tmp_path):
    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    flujo = crear_flujo(escenario, memoria, indice=crear_indice_demo())

    salida = flujo.invoke({"input": "/t24"}, config={"configurable": {
        "user_id": "ana", "session_id": sesion}})

    assert "Prueba T24 · recuperación ficticia" in salida.content
    assert "FIC-ENT-01-S05-C01" in salida.content
    assert "antes fuera del top-4; después 1" in salida.content
    assert "filtro `tema=entrega`" in salida.content
    assert "no puedo confirmar una recomendación" not in salida.content.lower()
