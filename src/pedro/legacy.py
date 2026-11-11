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


DESTINOS = {
    "catalogo": "buscar o describir una pieza por nombre, SKU o ID, sin hablar de precios",
    "comparacion": "precios, costes, ofertas, proveedores, stock o plazos de una pieza",
    "cep": "confirmar la ciudad o el estado de un código postal brasileño (CEP)",
}


def crear_router_llm(llm) -> RouterChain:
    """Router dinámico: el modelo elige el destino leyendo la descripción de cada ruta."""
    from langchain_classic.chains.router.llm_router import LLMRouterChain, RouterOutputParser
    from langchain_classic.chains.router.multi_prompt_prompt import MULTI_PROMPT_ROUTER_TEMPLATE
    from langchain_core.prompts import PromptTemplate

    destinos = "\n".join(f"{nombre}: {descripcion}" for nombre, descripcion in DESTINOS.items())
    plantilla = PromptTemplate(template=MULTI_PROMPT_ROUTER_TEMPLATE.format(destinations=destinos),
                               input_variables=["input"], output_parser=RouterOutputParser())
    return LLMRouterChain.from_llm(llm, plantilla)


def ejecutar_ruta(router: RouterChain, escenario: Escenario, pregunta: str, *,
                  cep_simulado: bool = True) -> dict:
    """Cadena secuencial: decide la ruta y ejecuta la cadena de ese destino."""
    from .integrations import consultar_cep

    ruta = router.invoke({"input": pregunta})["destination"] or "aclaracion"
    if ruta == "catalogo":
        return {"ruta": ruta, "resultado": buscar(escenario, pregunta)}
    if ruta == "comparacion":
        ids = re.findall(r"PEC-[0-9]{2}-[0-9]{4}", pregunta.upper())
        return {"ruta": ruta, "resultado": [o.model_dump() for o in ofertas(escenario, ids[0])]
                if ids else []}
    if ruta == "cep":
        codigos = re.findall(r"\b\d{5}-?\d{3}\b", pregunta)
        return {"ruta": ruta, "resultado": consultar_cep(codigos[0].replace("-", ""),
                                                         simulado=cep_simulado) if codigos else {}}
    return {"ruta": "aclaracion", "resultado": "¿Buscas una pieza, sus ofertas o un CEP?"}


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


PLANTILLA_CHATBOT = """Eres Pedro, asistente de un catálogo ficticio de repuestos de electrodomésticos.
Ayuda a concretar una solicitud de compra: pieza, cantidad, presupuesto y plazo. No inventes
precios ni stock: di que se consultarán en el catálogo. Responde en una o dos frases y recuerda
lo que el usuario ya dijo.

Conversación hasta ahora:
{history}
Usuario: {input}
Pedro:"""


def crear_chatbot_buffer(llm):
    """Chatbot conversacional clásico: ConversationChain con ConversationBufferMemory.

    La memoria de buffer guarda la conversación completa y la inserta entera en cada prompt.
    """
    from langchain_classic.chains import ConversationChain
    from langchain_core.prompts import PromptTemplate

    memoria = ConversationBufferMemory(human_prefix="Usuario", ai_prefix="Pedro")
    cadena = ConversationChain(
        llm=llm, memory=memoria,
        prompt=PromptTemplate(template=PLANTILLA_CHATBOT, input_variables=["history", "input"]))
    return cadena, memoria
