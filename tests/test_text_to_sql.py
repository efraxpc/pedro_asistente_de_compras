import json

import pytest
from langchain_core.runnables import RunnableLambda

from pedro.catalog import crear_escenario
from pedro.query import (MAX_FILAS, ConsultaRechazada, consultar_sql, crear_generador_sql,
                         responder_sql)


@pytest.fixture
def escenario(tmp_path):
    return crear_escenario(tmp_path / "catalogos")


def _generador(*consultas):
    salidas = iter(consultas)
    vistos = []

    def modelo(prompt):
        vistos.append(prompt.to_messages()[-1].content)
        return json.dumps({"sql": next(salidas), "explicacion": "prueba"})

    return crear_generador_sql(RunnableLambda(modelo)), vistos


def test_consulta_de_lectura_permitida_devuelve_filas(escenario):
    resultado = consultar_sql(escenario, "SELECT c.name, count(*) AS piezas FROM parts p "
                                         "JOIN categories c ON c.id = p.category_id GROUP BY c.name")
    assert len(resultado["filas"]) == 11 and sum(f["piezas"] for f in resultado["filas"]) == 2640
    assert resultado["dataset_id"] == escenario.dataset_id


@pytest.mark.parametrize("sql, motivo", [
    ("DROP TABLE offers", "solo se admiten consultas SELECT"),
    ("DELETE FROM offers", "solo se admiten consultas SELECT"),
    ("PRAGMA table_info(parts)", "solo se admiten consultas SELECT"),
    ("SELECT 1; DELETE FROM offers", "una sentencia"),
    ("SELECT id FROM parts -- comentario", "comentarios"),
    ("SELECT name FROM sqlite_master", "sqlite_master"),
    ("SELECT value FROM metadata", "metadata"),
    ("SELECT id, website FROM suppliers", "suppliers.website"),
    ("SELECT * FROM offers", "offers.currency"),
    ("SELECT load_extension('x')", "load_extension"),
    ("SELECT count(*) FROM parts a, parts b, parts c", "interrupted"),
])
def test_consultas_hostiles_o_fuera_del_esquema_se_rechazan(escenario, sql, motivo):
    with pytest.raises(ConsultaRechazada, match=motivo):
        consultar_sql(escenario, sql)
    assert consultar_sql(escenario, "SELECT count(*) AS n FROM offers")["filas"] == [{"n": 7920}]


def test_el_resultado_se_corta_en_el_limite_de_filas(escenario):
    resultado = consultar_sql(escenario, "SELECT id FROM parts")
    assert len(resultado["filas"]) == MAX_FILAS and resultado["truncado"]


def test_una_consulta_rechazada_se_corrige_una_vez_con_el_error(escenario):
    generador, vistos = _generador("SELECT * FROM suppliers",
                                   "SELECT id, name FROM suppliers ORDER BY id LIMIT 3")
    resultado = responder_sql(escenario, "¿Qué proveedores hay?", generador)
    assert resultado["estado"] == "ok" and len(resultado["filas"]) == 3
    assert [i["error"] is None for i in resultado["intentos"]] == [False, True]
    assert "suppliers.website" in vistos[1] and "SELECT * FROM suppliers" in vistos[1]


def test_dos_rechazos_no_devuelven_datos(escenario):
    generador, _ = _generador("DELETE FROM offers", "DROP TABLE offers")
    resultado = responder_sql(escenario, "Borra las ofertas", generador)
    assert resultado["estado"] == "rechazada" and resultado["filas"] == []
    assert consultar_sql(escenario, "SELECT count(*) AS n FROM offers")["filas"] == [{"n": 7920}]


def test_una_consulta_valida_sin_filas_se_senala(escenario):
    generador, _ = _generador("SELECT id FROM parts WHERE sku = 'PEC-01-0001'")
    assert responder_sql(escenario, "¿Existe PEC-01-0001?", generador)["estado"] == "sin_filas"
