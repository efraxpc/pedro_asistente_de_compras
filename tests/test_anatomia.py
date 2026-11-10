from pedro.anatomia import PAPELES, describir_anatomia, inventario_langchain
from pedro.catalog import crear_escenario


def test_anatomia_refleja_el_agente_construido(tmp_path):
    escenario = crear_escenario(tmp_path / "catalogos")
    anatomia = describir_anatomia(escenario, tmp_path / "memoria.sqlite3")
    assert {h["nombre"] for h in anatomia["herramientas"]} == set(PAPELES)
    assert all(anatomia["system_message"]["ptcf"].values())
    assert anatomia["orquestador"] == {
        "agente": "create_openai_tools_agent", "ejecutor": "AgentExecutor",
        "max_iteraciones": 6, "historial": "RunnableWithMessageHistory"}
    assert anatomia["base_conocimiento"]["dataset_id"] == escenario.dataset_id
    assert anatomia["base_conocimiento"]["piezas"] == 2640


def test_inventario_langchain_sale_de_los_imports_del_codigo():
    inventario = inventario_langchain()
    assert "create_openai_tools_agent" in inventario["agentes y ejecutor"]["nombres"]
    assert "agent.py" in inventario["agentes y ejecutor"]["archivos"]
    assert inventario["almacén vectorial (FAISS)"]["nombres"] == ["FAISS"]
    assert len(inventario) >= 10
