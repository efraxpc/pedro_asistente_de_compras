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


def test_router_por_reglas_y_router_llm_ejecutan_la_cadena_del_destino(tmp_path):
    from pedro.legacy import RouterCompras, crear_router_llm, ejecutar_ruta

    escenario = crear_escenario(tmp_path / "catalogos")
    reglas = RouterCompras()
    assert ejecutar_ruta(reglas, escenario, "precio de PEC-01-0001")["ruta"] == "comparacion"
    assert ejecutar_ruta(reglas, escenario, "Busca compresores")["ruta"] == "catalogo"

    def decide(destino):
        return FakeListLLM(responses=[
            '```json\n{"destination": "' + destino + '", "next_inputs": "pregunta"}\n```'])

    cep = ejecutar_ruta(crear_router_llm(decide("cep")), escenario, "CEP 01001-000")
    assert cep["ruta"] == "cep" and cep["resultado"]["modo"] == "simulado"
    ofertas = ejecutar_ruta(crear_router_llm(decide("comparacion")), escenario,
                            "¿Cuánto cuesta PEC-01-0001?")
    assert ofertas["ruta"] == "comparacion" and len(ofertas["resultado"]) == 3
    ninguna = ejecutar_ruta(crear_router_llm(decide("DEFAULT")), escenario, "Hola")
    assert ninguna["ruta"] == "aclaracion"


def test_chatbot_buffer_envia_todo_el_historial_en_cada_turno(tmp_path):
    from langchain_core.runnables import RunnableLambda

    from pedro.legacy import crear_chatbot_buffer

    prompts = []

    def modelo(prompt, **kwargs):
        prompts.append(prompt.to_string())
        return f"respuesta {len(prompts)}"

    chatbot, memoria = crear_chatbot_buffer(RunnableLambda(modelo))
    chatbot.invoke({"input": "Hola, soy Ana"})
    chatbot.invoke({"input": "Que sean 2 unidades"})
    salida = chatbot.invoke({"input": "¿Cómo me llamo?"})
    assert salida["response"] == "respuesta 3"
    assert "Hola, soy Ana" in prompts[2] and "Que sean 2 unidades" in prompts[2]
    assert "respuesta 1" in prompts[2] and "respuesta 2" in prompts[2]
    assert "respuesta" not in prompts[0]  # el primer turno aún no tiene historial
    historial = memoria.load_memory_variables({})["history"]
    assert historial.count("Usuario:") == 3 and historial.count("Pedro:") == 3
