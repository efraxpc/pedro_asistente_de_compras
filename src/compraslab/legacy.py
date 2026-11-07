"""APIs clásicas exigidas por la consigna, aisladas para enseñanza."""
from typing import Any

from langchain_classic.agents import AgentType, initialize_agent
from langchain_classic.chains.router.base import RouterChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.tools import Tool


class RouterCompras(RouterChain):
    """RouterChain concreto: envía intención a la cadena didáctica correspondiente."""
    @property
    def input_keys(self) -> list[str]:
        return ["input"]

    def _call(self, inputs: dict[str, Any], run_manager=None) -> dict[str, Any]:
        texto = inputs["input"].lower()
        if "política" in texto or "politica" in texto:
            destino = "politicas"
        elif "oferta" in texto or "precio" in texto:
            destino = "comparacion"
        else:
            destino = "aclaracion"
        return {"destination": destino, "next_inputs": {"input": inputs["input"]}}


def crear_react_textual(llm):
    """ReAct clásico con memoria de buffer; no se usa en el integrador final."""
    memoria = ConversationBufferMemory(memory_key="chat_history", input_key="input",
                                       output_key="output")
    herramienta = Tool(name="buscar_producto", func=lambda texto: f"Candidato: {texto}",
                       description="Busca un producto ficticio por nombre")
    agente = initialize_agent([herramienta], llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, memory=memoria,
        agent_kwargs={"prefix": "Historial previo: {chat_history}\n"
                                "Eres un asistente de compras ficticias. Usa herramientas si hace falta."})
    return agente, memoria
