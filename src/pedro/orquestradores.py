"""O mesmo agente pequeno em dois orquestradores: LangChain clássico e LangGraph.

Serve para comparar com uma execução, e não só em teoria, o que cada um exige e oferece.
Os dois recebem o mesmo modelo, as mesmas duas ferramentas e o mesmo prompt de sistema, e
expõem a mesma função `conversar(texto, fio)`. LangGraph é uma dependência opcional
(extra `comparacion`) e é importado somente ao construir esse agente.
"""
from collections.abc import Callable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from .catalog import Cenario, buscar, ofertas

SISTEMA = ("Você é Pedro, assistente de um catálogo fictício de peças de reposição. Use as ferramentas para "
           "buscar peças e consultar as ofertas delas; não invente dados. Responda em uma frase.")


def ferramentas_basicas(cenario: Cenario) -> list:
    @tool
    def buscar_peca(texto: str) -> str:
        """Busca peças por nome, SKU ou ID e devolve seus identificadores."""
        return str(buscar(cenario, texto, 5))

    @tool
    def ofertas_da_peca(produto_id: str) -> str:
        """Devolve fornecedor, preço em centavos, estoque e prazo em dias de uma peça pelo ID dela."""
        return str([{"fornecedor": o.fornecedor_nome, "preco_unitario_centavos": o.preco_unitario_centavos,
                     "estoque": o.estoque, "prazo_dias": o.prazo_dias} for o in ofertas(cenario, produto_id)])

    return [buscar_peca, ofertas_da_peca]


def agente_langchain(llm, cenario: Cenario) -> Callable[[str, str], dict]:
    """Agente com `create_openai_tools_agent`, `AgentExecutor` e `RunnableWithMessageHistory`."""
    from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
    from langchain_core.chat_history import InMemoryChatMessageHistory
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.runnables import RunnableWithMessageHistory

    lista = ferramentas_basicas(cenario)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SISTEMA), MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
    executor = AgentExecutor(agent=create_openai_tools_agent(llm, lista, prompt), tools=lista,
                             return_intermediate_steps=True, max_iterations=5)
    historicos: dict[str, InMemoryChatMessageHistory] = {}
    com_memoria = RunnableWithMessageHistory(
        executor, lambda fio: historicos.setdefault(fio, InMemoryChatMessageHistory()),
        input_messages_key="input", history_messages_key="chat_history", output_messages_key="output")

    def conversar(texto: str, fio: str) -> dict:
        saida = com_memoria.invoke({"input": texto}, config={"configurable": {"session_id": fio}})
        return {"resposta": saida["output"],
                "ferramentas": [f"{acao.tool}({acao.tool_input})"
                                for acao, _ in saida["intermediate_steps"]]}

    return conversar


def agente_langgraph(llm, cenario: Cenario) -> Callable[[str, str], dict]:
    """O mesmo agente com `create_agent` e um checkpointer em memória, como foi feito em aula."""
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver

    grafo = create_agent(llm, tools=ferramentas_basicas(cenario), system_prompt=SISTEMA,
                         checkpointer=InMemorySaver())

    def conversar(texto: str, fio: str) -> dict:
        config: RunnableConfig = {"configurable": {"thread_id": fio}}
        anteriores = len(grafo.get_state(config).values.get("messages", []))
        estado = grafo.invoke({"messages": [{"role": "user", "content": texto}]}, config)
        novos = estado["messages"][anteriores:]
        return {"resposta": str(novos[-1].content),
                "ferramentas": [f"{chamada['name']}({chamada['args']})" for mensagem in novos
                                for chamada in getattr(mensagem, "tool_calls", None) or []]}

    setattr(conversar, "grafo", grafo)  # para inspecionar o grafo de fora
    return conversar


def agente_com_langmem(llm, cenario: Cenario, embeddings, dimensao: int):
    """Agente LangGraph cuja memória de longo prazo é gerenciada pelo LangMem.

    O agente recebe duas ferramentas do LangMem: uma para criar, corrigir ou apagar lembranças e
    outra para buscá-las. É o próprio modelo que decide o que merece ser salvo. As lembranças
    vivem em um armazém por usuário. Devolve `conversar(texto, usuario, fio)` e o armazém.
    """
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.store.memory import InMemoryStore
    from langmem import create_manage_memory_tool, create_search_memory_tool

    armazem = InMemoryStore(index={"dims": dimensao, "embed": embeddings})
    espaco = ("lembrancas", "{user_id}")
    grafo = create_agent(
        llm, tools=[*ferramentas_basicas(cenario), create_manage_memory_tool(namespace=espaco),
                    create_search_memory_tool(namespace=espaco)],
        system_prompt=SISTEMA + " Você tem memória de longo prazo: use-a para lembrar o que o "
                                "usuário prefere e consulte-a quando perguntarem sobre isso.",
        checkpointer=InMemorySaver(), store=armazem)

    def conversar(texto: str, usuario: str, fio: str) -> dict:
        config: RunnableConfig = {"configurable": {"thread_id": fio, "user_id": usuario}}
        anteriores = len(grafo.get_state(config).values.get("messages", []))
        estado = grafo.invoke({"messages": [{"role": "user", "content": texto}]}, config)
        novos = estado["messages"][anteriores:]
        return {"resposta": str(novos[-1].content),
                "ferramentas": [f"{chamada['name']}({chamada['args']})" for mensagem in novos
                                for chamada in getattr(mensagem, "tool_calls", None) or []]}

    return conversar, armazem
