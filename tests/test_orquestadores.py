"""El mismo agente en dos orquestadores, con un modelo doble que pide una herramienta."""
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from pedro.catalog import crear_escenario
from pedro.orquestadores import agente_langchain, agente_langgraph, herramientas_basicas


class ModeloDoble(FakeMessagesListChatModel):
    """Devuelve mensajes guionados; aceptar `bind_tools` basta para montar un agente."""

    def bind_tools(self, tools, **kwargs):
        return self


def _guion():
    return ModeloDoble(responses=[
        AIMessage(content="", tool_calls=[{"name": "buscar_pieza", "args": {"texto": "NEVE-COMP-0001"},
                                           "id": "c1"}]),
        AIMessage(content="El ID es PEC-01-0001."),
        AIMessage(content="Hablábamos de PEC-01-0001."),
        AIMessage(content="No hemos hablado de ninguna pieza.")])


def test_las_herramientas_basicas_leen_el_catalogo(tmp_path):
    buscar, ofertas = herramientas_basicas(crear_escenario(tmp_path / "catalogos"))
    assert "PEC-01-0001" in buscar.invoke({"texto": "NEVE-COMP-0001"})
    assert "CentroPeças" in ofertas.invoke({"producto_id": "PEC-01-0001"})


@pytest.mark.parametrize("constructor", [agente_langchain, agente_langgraph])
def test_los_dos_orquestadores_ejecutan_la_herramienta_y_separan_los_hilos(tmp_path, constructor):
    if constructor is agente_langgraph:
        pytest.importorskip("langgraph")
    conversar = constructor(_guion(), crear_escenario(tmp_path / "catalogos"))
    primero = conversar("Busca NEVE-COMP-0001", "hilo-a")
    assert primero["respuesta"] == "El ID es PEC-01-0001."
    assert primero["herramientas"] == ["buscar_pieza({'texto': 'NEVE-COMP-0001'})"]
    assert conversar("¿De qué hablábamos?", "hilo-a")["herramientas"] == []
    assert conversar("¿De qué hablábamos?", "hilo-b")["respuesta"] == "No hemos hablado de ninguna pieza."


def test_langmem_guarda_por_usuario_lo_que_el_modelo_decide_recordar(tmp_path):
    pytest.importorskip("langmem")
    from langchain_core.embeddings import Embeddings

    from pedro.orquestadores import agente_con_langmem

    class Vectores(Embeddings):
        def embed_documents(self, texts):
            return [[1.0, 0.0, 0.0] for _ in texts]

        def embed_query(self, text):
            return [1.0, 0.0, 0.0]

    modelo = ModeloDoble(responses=[
        AIMessage(content="", tool_calls=[{"name": "manage_memory", "id": "m1", "args": {
            "content": "Prefiere proveedores nacionales.", "action": "create"}}]),
        AIMessage(content="Lo recordaré.")])
    conversar, almacen = agente_con_langmem(modelo, crear_escenario(tmp_path / "catalogos"),
                                            Vectores(), 3)
    turno = conversar("Prefiero proveedores nacionales, recuérdalo", "ana", "hilo-1")
    assert turno["respuesta"] == "Lo recordaré." and turno["herramientas"][0].startswith("manage_memory")
    assert [item.value["content"] for item in almacen.search(("recuerdos", "ana"))] == [
        "Prefiere proveedores nacionales."]
    assert almacen.search(("recuerdos", "luis")) == []
