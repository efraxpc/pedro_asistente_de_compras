import json

from compraslab.data import buscar_productos as buscar_sql, crear_catalogo
from compraslab.semantic_parts import buscar_piezas_semanticas, indexar_piezas
from compraslab.tools import buscar_productos


class EmbeddingsFicticios:
    def __init__(self):
        self.consultas = 0

    def embed_documents(self, texts):
        return [[1.0, 0.0] if "Compresor" in text else [0.0, 1.0]
                for text in texts]

    def embed_query(self, text):
        self.consultas += 1
        return [1.0, 0.0]


def test_busqueda_semantica_aislada_y_exacta(tmp_path):
    embeddings = EmbeddingsFicticios()
    index_dir = tmp_path / "indice"
    assert indexar_piezas(embeddings, index_dir=index_dir) == 2640
    catalogo = crear_catalogo(tmp_path / "catalogos", cantidad=4)

    assert buscar_sql(catalogo, "refrigeración averiada") == []
    encontrados = buscar_piezas_semanticas(
        catalogo, "refrigeración averiada", embeddings, index_dir=index_dir)
    assert encontrados[0].id == "PROD-0001"
    assert len(encontrados) == 4
    assert all(p.dataset_id == catalogo.dataset_id for p in encontrados)

    resultado = buscar_productos(catalogo, "refrigeración averiada",
                                 embeddings=embeddings, index_dir=index_dir)
    assert resultado.estado == "ok"
    assert resultado.datos[0]["id"] == "PROD-0001"
    assert resultado.evidencias[0].dataset_id == catalogo.dataset_id
    consultas = embeddings.consultas
    exacto = buscar_productos(catalogo, "NEVE-TERM-0002",
                              embeddings=embeddings, index_dir=index_dir)
    assert [p["id"] for p in exacto.datos] == ["PROD-0002"]
    assert embeddings.consultas == consultas


def test_indice_desactualizado_y_falta_de_indice_usan_sql(tmp_path, monkeypatch):
    embeddings = EmbeddingsFicticios()
    catalogo = crear_catalogo(tmp_path / "catalogos", cantidad=4)
    ausente = buscar_productos(catalogo, "NEVE-TERM", embeddings=embeddings,
                               index_dir=tmp_path / "ausente")
    assert ausente.estado == "ok"
    assert embeddings.consultas == 0

    index_dir = tmp_path / "indice"
    indexar_piezas(embeddings, index_dir=index_dir)
    manifest_path = index_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["source_sha256"] = "incorrecto"
    manifest_path.write_text(json.dumps(manifest))
    resultado = buscar_productos(catalogo, "NEVE-TERM", embeddings=embeddings,
                                 index_dir=index_dir)
    assert [p["id"] for p in resultado.datos] == ["PROD-0002"]
    assert embeddings.consultas == 0

    indexar_piezas(embeddings, index_dir=index_dir)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sin_clave = buscar_productos(catalogo, "NEVE-TERM", index_dir=index_dir)
    assert [p["id"] for p in sin_clave.datos] == ["PROD-0002"]

    class EmbeddingsFallidos(EmbeddingsFicticios):
        def embed_query(self, text):
            raise RuntimeError("API no disponible")

    fallida = buscar_productos(catalogo, "NEVE-TERM",
                               embeddings=EmbeddingsFallidos(), index_dir=index_dir)
    assert [p["id"] for p in fallida.datos] == ["PROD-0002"]
