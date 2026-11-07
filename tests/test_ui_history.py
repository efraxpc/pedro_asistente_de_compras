from pathlib import Path
from dataclasses import replace

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from streamlit.testing.v1 import AppTest

from compraslab.memory import HistorialSQLite, listar_sesiones, mensajes_sesion, nueva_sesion


def test_lista_y_historial_completo_aislados(tmp_path: Path):
    ruta = tmp_path / "memoria.sqlite3"
    primera = nueva_sesion(ruta, "u1", "dataset-a")
    segunda = nueva_sesion(ruta, "u1", "dataset-b")
    ajena = nueva_sesion(ruta, "u2", "dataset-a")
    HistorialSQLite(ruta, primera, "u1").add_messages(
        [HumanMessage(content="Comprar monitor\nurgente")]
        + [AIMessage(content=f"respuesta {i}") for i in range(13)])
    HistorialSQLite(ruta, ajena, "u2").add_messages([HumanMessage(content="Privado")])

    assert [s["session_id"] for s in listar_sesiones(ruta, "u1")] == [primera, segunda]
    assert listar_sesiones(ruta, "u1")[0]["titulo"] == "Comprar monitor urgente"
    assert listar_sesiones(ruta, "u1")[1]["titulo"] == "Nuevo chat"
    assert len(mensajes_sesion(ruta, primera, "u1")) == 14
    assert len(HistorialSQLite(ruta, primera, "u1").messages) == 12
    with pytest.raises(ValueError):
        mensajes_sesion(ruta, ajena, "u1")


def test_app_muestra_chat_y_comparacion_sin_clave(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("COMPRASLAB_CATALOG_SOURCE", "dummyjson")
    app = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=20).run()

    assert not at.exception
    assert any("Pedro" in title.value for title in at.title)
    assert not at.chat_input[0].disabled
    assert len(at.sidebar.button) >= 3
    at.chat_input[0].set_value("¿Cuál es tu fuente de datos?").run()
    assert not at.exception
    mensajes = HistorialSQLite(tmp_path / "storage" / "memoria.sqlite3",
                              at.session_state["session_id"], "usuario-demo").messages
    assert "base SQLite local" in mensajes[-1].content
    assert at.session_state["catalogo"].modo == "piezas"
    primera = at.session_state["session_id"]
    dataset = at.session_state["catalogo"].dataset_id
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert at.session_state["session_id"] != primera
    assert at.session_state["catalogo"].dataset_id == dataset
    at.sidebar.button(key=f"chat_{primera}").click().run()
    assert not at.exception
    assert at.session_state["session_id"] == primera
    assert at.session_state["catalogo"].dataset_id == dataset
    at.sidebar.segmented_control[0].set_value("Comparación local").run()
    assert not at.exception
    assert any("Comparación local" in title.value for title in at.title)
    at.sidebar.button[1].click().run()
    assert not at.exception
    assert at.session_state["catalogo"].dataset_id != dataset
    assert at.session_state["vista"] == "Chat"


def test_app_permite_ver_todas_las_piezas_y_sus_detalles(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("COMPRASLAB_CATALOG_SOURCE", "piezas")
    app = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=20).run()
    at.sidebar.segmented_control[0].set_value("Catálogo de piezas").run()
    assert not at.exception
    assert at.dataframe[0].value.shape[0] == 2640
    at.selectbox[0].select("Neveras").run()
    assert not at.exception
    assert at.dataframe[0].value.shape[0] == 240
    sku = at.dataframe[0].value.iloc[0]["SKU"]
    at.selectbox[1].select(sku).run()
    assert not at.exception
    assert len(at.dataframe) == 5
    assert at.dataframe[3].value.shape[0] == 3
    assert at.dataframe[4].value.shape[0] == 18


def test_sesion_activa_anterior_se_reemplaza_por_sqlite(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    app = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=20).run()
    anterior = at.session_state["catalogo"].dataset_id
    at.session_state["catalogo"] = replace(at.session_state["catalogo"], modo="dummyjson")
    at.run()
    assert not at.exception
    assert at.session_state["catalogo"].modo == "piezas"
    assert at.session_state["catalogo"].dataset_id != anterior
    assert at.session_state["vista"] == "Chat"
