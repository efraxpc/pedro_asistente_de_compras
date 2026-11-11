"""El mismo agente pequeño en dos orquestadores: LangChain clásico y LangGraph.

Sirve para comparar con una ejecución, y no solo en teoría, lo que cada uno exige y ofrece.
Los dos reciben el mismo modelo, las mismas dos herramientas y el mismo prompt de sistema, y
exponen la misma función `conversar(texto, hilo)`. LangGraph es una dependencia opcional
(extra `comparacion`) y se importa solo al construir ese agente.
"""
from collections.abc import Callable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from .catalog import Escenario, buscar, ofertas

SISTEMA = ("Eres Pedro, asistente de un catálogo ficticio de repuestos. Usa las herramientas para "
           "buscar piezas y consultar sus ofertas; no inventes datos. Responde en una frase.")


def herramientas_basicas(escenario: Escenario) -> list:
    @tool
    def buscar_pieza(texto: str) -> str:
        """Busca piezas por nombre, SKU o ID y devuelve sus identificadores."""
        return str(buscar(escenario, texto, 5))

    @tool
    def ofertas_de_pieza(producto_id: str) -> str:
        """Devuelve proveedor, precio en centavos, stock y plazo en días de una pieza por su ID."""
        return str([{"proveedor": o.proveedor_nombre, "precio_unitario_centavos": o.precio_unitario_centavos,
                     "stock": o.stock, "plazo_dias": o.plazo_dias} for o in ofertas(escenario, producto_id)])

    return [buscar_pieza, ofertas_de_pieza]


def agente_langchain(llm, escenario: Escenario) -> Callable[[str, str], dict]:
    """Agente con `create_openai_tools_agent`, `AgentExecutor` y `RunnableWithMessageHistory`."""
    from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
    from langchain_core.chat_history import InMemoryChatMessageHistory
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.runnables import RunnableWithMessageHistory

    lista = herramientas_basicas(escenario)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SISTEMA), MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
    ejecutor = AgentExecutor(agent=create_openai_tools_agent(llm, lista, prompt), tools=lista,
                             return_intermediate_steps=True, max_iterations=5)
    historiales: dict[str, InMemoryChatMessageHistory] = {}
    con_memoria = RunnableWithMessageHistory(
        ejecutor, lambda hilo: historiales.setdefault(hilo, InMemoryChatMessageHistory()),
        input_messages_key="input", history_messages_key="chat_history", output_messages_key="output")

    def conversar(texto: str, hilo: str) -> dict:
        salida = con_memoria.invoke({"input": texto}, config={"configurable": {"session_id": hilo}})
        return {"respuesta": salida["output"],
                "herramientas": [f"{accion.tool}({accion.tool_input})"
                                 for accion, _ in salida["intermediate_steps"]]}

    return conversar


def agente_langgraph(llm, escenario: Escenario) -> Callable[[str, str], dict]:
    """El mismo agente con `create_agent` y un checkpointer en memoria, como se hizo en clase."""
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver

    grafo = create_agent(llm, tools=herramientas_basicas(escenario), system_prompt=SISTEMA,
                         checkpointer=InMemorySaver())

    def conversar(texto: str, hilo: str) -> dict:
        config: RunnableConfig = {"configurable": {"thread_id": hilo}}
        previos = len(grafo.get_state(config).values.get("messages", []))
        estado = grafo.invoke({"messages": [{"role": "user", "content": texto}]}, config)
        nuevos = estado["messages"][previos:]
        return {"respuesta": str(nuevos[-1].content),
                "herramientas": [f"{llamada['name']}({llamada['args']})" for mensaje in nuevos
                                 for llamada in getattr(mensaje, "tool_calls", None) or []]}

    setattr(conversar, "grafo", grafo)  # para inspeccionar el grafo desde fuera
    return conversar


def agente_con_langmem(llm, escenario: Escenario, embeddings, dimension: int):
    """Agente LangGraph cuya memoria de largo plazo la gestiona LangMem.

    El agente recibe dos herramientas de LangMem: una para crear, corregir o borrar recuerdos y
    otra para buscarlos. Es el propio modelo quien decide qué merece guardarse. Los recuerdos
    viven en un almacén por usuario. Devuelve `conversar(texto, usuario, hilo)` y el almacén.
    """
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.store.memory import InMemoryStore
    from langmem import create_manage_memory_tool, create_search_memory_tool

    almacen = InMemoryStore(index={"dims": dimension, "embed": embeddings})
    espacio = ("recuerdos", "{user_id}")
    grafo = create_agent(
        llm, tools=[*herramientas_basicas(escenario), create_manage_memory_tool(namespace=espacio),
                    create_search_memory_tool(namespace=espacio)],
        system_prompt=SISTEMA + " Tienes memoria de largo plazo: úsala para recordar lo que el "
                                "usuario prefiere y consúltala cuando te pregunten por ello.",
        checkpointer=InMemorySaver(), store=almacen)

    def conversar(texto: str, usuario: str, hilo: str) -> dict:
        config: RunnableConfig = {"configurable": {"thread_id": hilo, "user_id": usuario}}
        previos = len(grafo.get_state(config).values.get("messages", []))
        estado = grafo.invoke({"messages": [{"role": "user", "content": texto}]}, config)
        nuevos = estado["messages"][previos:]
        return {"respuesta": str(nuevos[-1].content),
                "herramientas": [f"{llamada['name']}({llamada['args']})" for mensaje in nuevos
                                 for llamada in getattr(mensaje, "tool_calls", None) or []]}

    return conversar, almacen
