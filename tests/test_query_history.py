from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import ConfigurableFieldSpec, RunnableLambda, RunnableWithMessageHistory

from compraslab.data import crear_catalogo
from compraslab.memory import HistorialSQLite, nueva_sesion
from compraslab.query import PlanConsulta, ejecutar_plan, text_to_query


def test_consulta_parametrizada_y_acotada(tmp_path):
    catalogo = crear_catalogo(tmp_path / "catalogos", cantidad=4, semilla=42)
    resultado = text_to_query(catalogo, "¿Qué ofertas tiene PROD-003?")
    assert resultado.estado == "ok"
    assert resultado.datos["validacion"] == "plantilla permitida"
    assert resultado.datos["parametros"][0] == catalogo.dataset_id
    assert len(resultado.datos["filas"]) == 3
    assert text_to_query(catalogo, "DROP TABLE producto").estado == "invalido"
    assert len(ejecutar_plan(catalogo, PlanConsulta(objetivo="ofertas", producto_id="PROD-003", limite=1)).datos["filas"]) == 1


def test_historial_langchain_persistente_y_aislado(tmp_path):
    ruta = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(ruta, "u1", "dataset-a")
    otra = nueva_sesion(ruta, "u2", "dataset-a")
    def get_history(user_id: str, session_id: str):
        return HistorialSQLite(ruta, session_id, user_id)
    def responder(dato):
        return AIMessage(content=f"recibido: {dato['input']}; previos: {len(dato['chat_history'])}")
    wrapped = RunnableWithMessageHistory(RunnableLambda(responder), get_history,
        input_messages_key="input", history_messages_key="chat_history",
        history_factory_config=[ConfigurableFieldSpec(id="user_id", annotation=str, name="usuario"),
                                ConfigurableFieldSpec(id="session_id", annotation=str, name="sesión")])
    cfg = {"configurable": {"user_id": "u1", "session_id": sesion}}
    assert "previos: 0" in wrapped.invoke({"input": "hola"}, config=cfg).content
    assert "previos: 2" in wrapped.invoke({"input": "otra"}, config=cfg).content
    assert len(HistorialSQLite(ruta, sesion, "u1").messages) == 4
    assert HistorialSQLite(ruta, otra, "u2").messages == []
