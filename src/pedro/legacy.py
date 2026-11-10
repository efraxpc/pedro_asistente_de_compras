"""APIs clásicas aisladas para las demostraciones del curso."""
import re
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
    ids = re.findall(r"PEC-[0-9]{2}-[0-9]{4}", pregunta.upper())
    return {"ruta": ruta, "resultado": [o.model_dump() for o in ofertas(escenario, ids[0])]
            if ids else []}


SUFIJO_CON_MEMORIA = """Conversación previa (úsala para entender a qué pieza se refiere el usuario):
{chat_history}

Empieza.

Question: {input}
Thought:{agent_scratchpad}"""


def crear_react_textual(llm, escenario: Escenario, *, memoria_en_prompt: bool = True):
    """Agente ReAct clásico (zero-shot) con dos herramientas del catálogo y memoria de buffer.

    El prompt zero-shot original no incluye el historial: la memoria se guarda pero el modelo
    no la lee. Con `memoria_en_prompt` se añade `{chat_history}` al sufijo del prompt.
    """
    memoria = ConversationBufferMemory(memory_key="chat_history", input_key="input", output_key="output")

    def ofertas_de_pieza(texto: str) -> str:
        ids = re.findall(r"PEC-[0-9]{2}-[0-9]{4}", texto.upper())
        if not ids:
            return "Indica un ID con formato PEC-00-0000."
        return str([{"proveedor": o.proveedor_nombre, "precio_unitario_centavos": o.precio_unitario_centavos,
                     "stock": o.stock, "plazo_dias": o.plazo_dias} for o in ofertas(escenario, ids[0])])

    lista = [
        Tool(name="buscar_pieza", func=lambda texto: str(buscar(escenario, texto, 5)),
             description="Busca piezas ficticias por nombre, SKU o ID. Entrada: texto de búsqueda."),
        Tool(name="ofertas_de_pieza", func=ofertas_de_pieza,
             description="Devuelve proveedor, precio, stock y plazo de una pieza. Entrada: su ID PEC-00-0000."),
    ]
    extra = ({"suffix": SUFIJO_CON_MEMORIA,
              "input_variables": ["input", "chat_history", "agent_scratchpad"]}
             if memoria_en_prompt else {})
    agente = initialize_agent(lista, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                              memory=memoria, verbose=False, agent_kwargs=extra,
                              return_intermediate_steps=True, handle_parsing_errors=True,
                              max_iterations=5)
    return agente, memoria
