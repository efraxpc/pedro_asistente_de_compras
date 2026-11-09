"""APIs clásicas aisladas para las demostraciones del curso."""
from typing import Any

from langchain_classic.agents import AgentType, initialize_agent
from langchain_classic.chains.router.base import RouterChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.tools import Tool

from .catalog import Escenario, buscar, ofertas


class RouterCompras(RouterChain):
    @property
    def input_keys(self) -> list[str]:
        return ["input"]

    def _call(self, inputs: dict[str, Any], run_manager=None) -> dict[str, Any]:
        texto = inputs["input"].lower()
        destino = "comparacion" if any(x in texto for x in ("oferta", "precio", "stock")) else "catalogo"
        return {"destination": destino, "next_inputs": {"input": inputs["input"]}}


def ejecutar_ruta(router: RouterCompras, escenario: Escenario, pregunta: str) -> dict:
    ruta = router.invoke({"input": pregunta})["destination"]
    if ruta == "catalogo":
        return {"ruta": ruta, "resultado": buscar(escenario, pregunta)}
    import re
    ids = re.findall(r"PEC-[0-9]{2}-[0-9]{4}", pregunta.upper())
    return {"ruta": ruta, "resultado": [o.model_dump() for o in ofertas(escenario, ids[0])]
            if ids else []}


def crear_react_textual(llm, escenario: Escenario):
    memoria = ConversationBufferMemory(memory_key="chat_history", input_key="input", output_key="output")
    herramienta = Tool(name="buscar_pieza", func=lambda texto: str(buscar(escenario, texto)),
                       description="Busca piezas ficticias en el escenario")
    agente = initialize_agent([herramienta], llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                              memory=memoria, verbose=False)
    return agente, memoria
