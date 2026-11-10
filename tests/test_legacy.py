from langchain_core.language_models.fake import FakeListLLM

from pedro.catalog import crear_escenario
from pedro.legacy import crear_react_textual

GUION = ["Thought: busco\nAction: buscar_pieza\nAction Input: NEVE-COMP-0001",
         "Thought: listo\nFinal Answer: el ID es PEC-01-0001",
         "Thought: uso el historial\nAction: ofertas_de_pieza\nAction Input: PEC-01-0001",
         "Thought: listo\nFinal Answer: CentroPeças entrega en 2 días"]


def test_react_clasico_ejecuta_herramientas_y_guarda_memoria(tmp_path):
    escenario = crear_escenario(tmp_path / "catalogos")
    agente, memoria = crear_react_textual(FakeListLLM(responses=GUION), escenario)
    primero = agente.invoke({"input": "Busca NEVE-COMP-0001"})
    segundo = agente.invoke({"input": "¿Quién entrega más rápido?"})
    assert [a.tool for a, _ in primero["intermediate_steps"]] == ["buscar_pieza"]
    assert "PEC-01-0001" in primero["intermediate_steps"][0][1]
    accion, observacion = segundo["intermediate_steps"][0]
    assert accion.tool == "ofertas_de_pieza" and "CentroPeças" in observacion
    historial = memoria.load_memory_variables({})["chat_history"]
    assert "Busca NEVE-COMP-0001" in historial and "el ID es PEC-01-0001" in historial


def test_el_historial_solo_llega_al_modelo_si_el_prompt_lo_incluye(tmp_path):
    escenario = crear_escenario(tmp_path / "catalogos")
    con, _ = crear_react_textual(FakeListLLM(responses=GUION), escenario)
    sin, _ = crear_react_textual(FakeListLLM(responses=GUION), escenario, memoria_en_prompt=False)
    assert "chat_history" in con.agent.llm_chain.prompt.input_variables
    assert "chat_history" not in sin.agent.llm_chain.prompt.input_variables
