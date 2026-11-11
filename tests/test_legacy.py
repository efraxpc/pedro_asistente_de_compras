from langchain_core.language_models.fake import FakeListLLM

from pedro.catalog import criar_cenario
from pedro.legacy import criar_react_textual

ROTEIRO = ["Thought: busco\nAction: buscar_peca\nAction Input: GELA-COMP-0001",
           "Thought: pronto\nFinal Answer: o ID é PEC-01-0001",
           "Thought: uso o histórico\nAction: ofertas_da_peca\nAction Input: PEC-01-0001",
           "Thought: pronto\nFinal Answer: CentroPeças entrega em 2 dias"]


def test_react_classico_executa_ferramentas_e_salva_memoria(tmp_path):
    cenario = criar_cenario(tmp_path / "catalogos")
    agente, memoria = criar_react_textual(FakeListLLM(responses=ROTEIRO), cenario)
    primeiro = agente.invoke({"input": "Busque GELA-COMP-0001"})
    segundo = agente.invoke({"input": "Quem entrega mais rápido?"})
    assert [a.tool for a, _ in primeiro["intermediate_steps"]] == ["buscar_peca"]
    assert "PEC-01-0001" in primeiro["intermediate_steps"][0][1]
    acao, observacao = segundo["intermediate_steps"][0]
    assert acao.tool == "ofertas_da_peca" and "CentroPeças" in observacao
    historico = memoria.load_memory_variables({})["chat_history"]
    assert "Busque GELA-COMP-0001" in historico and "o ID é PEC-01-0001" in historico


def test_o_historico_so_chega_ao_modelo_se_o_prompt_o_inclui(tmp_path):
    cenario = criar_cenario(tmp_path / "catalogos")
    com, _ = criar_react_textual(FakeListLLM(responses=ROTEIRO), cenario)
    sem, _ = criar_react_textual(FakeListLLM(responses=ROTEIRO), cenario, memoria_no_prompt=False)
    assert "chat_history" in com.agent.llm_chain.prompt.input_variables
    assert "chat_history" not in sem.agent.llm_chain.prompt.input_variables


def test_router_por_regras_e_router_llm_executam_a_cadeia_do_destino(tmp_path):
    from pedro.legacy import RouterCompras, criar_router_llm, executar_rota

    cenario = criar_cenario(tmp_path / "catalogos")
    regras = RouterCompras()
    assert executar_rota(regras, cenario, "preço de PEC-01-0001")["rota"] == "comparacao"
    assert executar_rota(regras, cenario, "Busque compressores")["rota"] == "catalogo"

    def decide(destino):
        return FakeListLLM(responses=[
            '```json\n{"destination": "' + destino + '", "next_inputs": "pergunta"}\n```'])

    cep = executar_rota(criar_router_llm(decide("cep")), cenario, "CEP 01001-000")
    assert cep["rota"] == "cep" and cep["resultado"]["modo"] == "simulado"
    ofertas = executar_rota(criar_router_llm(decide("comparacao")), cenario,
                            "Quanto custa PEC-01-0001?")
    assert ofertas["rota"] == "comparacao" and len(ofertas["resultado"]) == 3
    nenhuma = executar_rota(criar_router_llm(decide("DEFAULT")), cenario, "Olá")
    assert nenhuma["rota"] == "esclarecimento"


def test_chatbot_buffer_envia_todo_o_historico_em_cada_turno(tmp_path):
    from langchain_core.runnables import RunnableLambda

    from pedro.legacy import criar_chatbot_buffer

    prompts = []

    def modelo(prompt, **kwargs):
        prompts.append(prompt.to_string())
        return f"resposta {len(prompts)}"

    chatbot, memoria = criar_chatbot_buffer(RunnableLambda(modelo))
    chatbot.invoke({"input": "Olá, sou a Ana"})
    chatbot.invoke({"input": "Que sejam 2 unidades"})
    saida = chatbot.invoke({"input": "Como eu me chamo?"})
    assert saida["response"] == "resposta 3"
    assert "Olá, sou a Ana" in prompts[2] and "Que sejam 2 unidades" in prompts[2]
    assert "resposta 1" in prompts[2] and "resposta 2" in prompts[2]
    assert "resposta" not in prompts[0]  # o primeiro turno ainda não tem histórico
    historico = memoria.load_memory_variables({})["history"]
    assert historico.count("Usuário:") == 3 and historico.count("Pedro:") == 3
