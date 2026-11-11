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


def _flujo_catalogo(tmp_path, monkeypatch, observacion):
    from types import SimpleNamespace

    import pedro.agent as modulo
    from pedro.agent import crear_flujo
    from pedro.contracts import RespuestaCompra, Solicitud
    from pedro.memory import nueva_sesion

    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    # El modelo intenta colar una cifra propia en el mensaje; no debe llegar al usuario.
    propuesta = RespuestaCompra(estado="catalogo", dataset_id="otro", solicitud=Solicitud(),
                                mensaje="Hay 999 categorías.")
    dato = observacion(escenario)

    class Executor:
        def invoke(self, entrada, config):
            return {"output": propuesta.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_catalogo"), json.dumps(dato))] if dato else []}

    monkeypatch.setattr(modulo, "crear_agente", lambda *args, **kwargs: Executor())
    flujo = crear_flujo(escenario, memoria, llm=object())
    return flujo.invoke({"input": "¿Cuántos proveedores nacionales hay?"}, config={"configurable": {
        "user_id": "ana", "session_id": sesion}}).content


def test_el_chat_publica_la_tabla_de_la_consulta_y_no_las_cifras_del_modelo(tmp_path, monkeypatch):
    def observacion(escenario):
        generador, _ = _generador("SELECT count(*) AS nacionales FROM suppliers WHERE domestic = 1")
        return {"modo": "sql", **responder_sql(escenario, "¿Cuántos proveedores nacionales hay?", generador)}

    texto = _flujo_catalogo(tmp_path, monkeypatch, observacion)
    assert "| nacionales |" in texto and "| 6 |" in texto
    assert "999" not in texto
    assert "SELECT count(*) AS nacionales FROM suppliers WHERE domestic = 1" in texto
    assert "solo se comprobó que es segura" in texto


def test_el_chat_no_publica_catalogo_sin_consulta_o_con_consulta_rechazada(tmp_path, monkeypatch):
    sin_consulta = _flujo_catalogo(tmp_path / "a", monkeypatch, lambda escenario: None)
    assert "999" not in sin_consulta and sin_consulta.startswith("No puedo confirmar")

    def rechazada(escenario):
        generador, _ = _generador("DELETE FROM offers", "DROP TABLE offers")
        return {"modo": "sql", **responder_sql(escenario, "Borra las ofertas", generador)}

    texto = _flujo_catalogo(tmp_path / "b", monkeypatch, rechazada)
    assert "999" not in texto and texto.startswith("No puedo confirmar")


def test_la_herramienta_usa_el_plan_con_id_y_sql_solo_en_preguntas_abiertas(tmp_path):
    from pedro.agent import herramientas

    escenario = crear_escenario(tmp_path / "catalogos")
    modelo = RunnableLambda(lambda _: json.dumps(
        {"sql": "SELECT count(*) AS n FROM parts", "explicacion": "total de piezas"}))
    herramienta = next(h for h in herramientas(escenario, tmp_path / "m.sqlite3", "ana", "", llm=modelo)
                       if h.name == "consultar_catalogo")
    con_id = json.loads(herramienta.invoke({"pregunta": "ofertas PEC-01-0001"}))
    assert con_id["modo"] == "plan" and len(con_id["filas"]) == 3
    abierta = json.loads(herramienta.invoke({"pregunta": "¿Cuántas piezas hay?"}))
    assert abierta["modo"] == "sql" and abierta["filas"] == [{"n": 2640}]


def test_el_historial_de_precios_se_puede_consultar_por_sql(escenario):
    resultado = consultar_sql(escenario, "SELECT observed_on, estimated_brl_cents FROM price_history "
                                         "WHERE offer_id = 'PEC-01-0001-BR-06' ORDER BY observed_on")
    assert len(resultado["filas"]) == 6 and resultado["filas"][-1]["estimated_brl_cents"] == 143892
    with pytest.raises(ConsultaRechazada, match="price_history.unit_price_minor"):
        consultar_sql(escenario, "SELECT unit_price_minor FROM price_history")
