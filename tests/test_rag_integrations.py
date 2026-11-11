import hashlib
import json

import pytest

from pedro.integrations import consultar_cep
from pedro.query import planejar
from pedro.rag import carregar_indice, inspecionar_indice


def test_indice_exige_impressao_e_confianca(tmp_path):
    arquivos = {}
    for nome in ("index.faiss", "index.pkl"):
        conteudo = nome.encode()
        (tmp_path / nome).write_bytes(conteudo)
        arquivos[nome] = hashlib.sha256(conteudo).hexdigest()
    meta = {"origem": "fixture", "embedding_model": "modelo-test", "dimension": 4,
            "metrica": "L2", "documentos": [{"id": "doc-1", "metadata": {"source": "fixture"}}],
            "sha256": arquivos}
    (tmp_path / "manifest.json").write_text(json.dumps(meta))
    assert inspecionar_indice(tmp_path)["dimension"] == 4
    with pytest.raises(PermissionError):
        carregar_indice(tmp_path, object(), origem_confiavel=False)
    (tmp_path / "index.pkl").write_bytes(b"alterado")
    with pytest.raises(ValueError, match="impressão digital"):
        inspecionar_indice(tmp_path)


def test_plano_rejeita_sql_livre_e_viacep_duplo():
    with pytest.raises(ValueError):
        planejar("ofertas PEC-01-0001; DROP TABLE offers; PEC-01-0002")
    assert consultar_cep("123")["estado"] == "invalido"
    assert consultar_cep("01001000", simulado=True)["modo"] == "simulado"
