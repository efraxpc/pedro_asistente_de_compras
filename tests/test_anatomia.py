from pedro.anatomia import PAPEIS, descrever_anatomia, inventario_langchain
from pedro.catalog import criar_cenario


def test_anatomia_reflete_o_agente_construido(tmp_path):
    cenario = criar_cenario(tmp_path / "catalogos")
    anatomia = descrever_anatomia(cenario, tmp_path / "memoria.sqlite3")
    assert {f["nome"] for f in anatomia["ferramentas"]} == set(PAPEIS)
    assert all(anatomia["system_message"]["ptcf"].values())
    assert anatomia["orquestrador"] == {
        "agente": "create_openai_tools_agent", "executor": "AgentExecutor",
        "max_iteracoes": 6, "historico": "RunnableWithMessageHistory"}
    assert anatomia["base_conhecimento"]["dataset_id"] == cenario.dataset_id
    assert anatomia["base_conhecimento"]["pecas"] == 2640


def test_inventario_langchain_sai_dos_imports_do_codigo():
    inventario = inventario_langchain()
    assert "create_openai_tools_agent" in inventario["agentes e executor"]["nomes"]
    assert "agent.py" in inventario["agentes e executor"]["arquivos"]
    assert inventario["armazém vetorial (FAISS)"]["nomes"] == ["FAISS"]
    assert len(inventario) >= 10
