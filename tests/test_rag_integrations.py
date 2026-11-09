import hashlib
import json

import pytest

from pedro.integrations import consultar_cep
from pedro.query import planear
from pedro.rag import cargar_indice, inspeccionar_indice


def test_indice_exige_huella_y_confianza(tmp_path):
    archivos = {}
    for nombre in ("index.faiss", "index.pkl"):
        contenido = nombre.encode()
        (tmp_path / nombre).write_bytes(contenido)
        archivos[nombre] = hashlib.sha256(contenido).hexdigest()
    meta = {"origen": "fixture", "embedding_model": "modelo-test", "dimension": 4,
            "metrica": "L2", "documentos": [{"id": "doc-1", "metadata": {"source": "fixture"}}],
            "sha256": archivos}
    (tmp_path / "manifest.json").write_text(json.dumps(meta))
    assert inspeccionar_indice(tmp_path)["dimension"] == 4
    with pytest.raises(PermissionError):
        cargar_indice(tmp_path, object(), origen_confiable=False)
    (tmp_path / "index.pkl").write_bytes(b"alterado")
    with pytest.raises(ValueError, match="huella"):
        inspeccionar_indice(tmp_path)


def test_plan_rechaza_sql_libre_y_viacep_doble():
    with pytest.raises(ValueError):
        planear("ofertas PEC-01-0001; DROP TABLE offers; PEC-01-0002")
    assert consultar_cep("123")["estado"] == "invalido"
    assert consultar_cep("01001000", simulado=True)["modo"] == "simulado"
