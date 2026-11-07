"""Agente clásico y publicación posterior a verificación; requiere modelo configurado."""
from pathlib import Path
from typing import Callable
import json
import re

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import ConfigurableFieldSpec, RunnableLambda, RunnableWithMessageHistory
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI

from .data import Catalogo
from .business import formatar_brl
from .integrations import consultar_cep
from .memory import (HistorialSQLite, guardar_episodio, guardar_preferencia,
                     preferencias, recuperar_episodios)
from .query import text_to_query
from .prompts import EJEMPLOS_TEXTO
from .schemas import RespuestaCompra, SolicitudCompra
from .tools import buscar_productos, comparar, consultar_politicas
from .verification import verificar


def crear_agente(catalogo: Catalogo, model: str = "gpt-4.1-mini", *, indice=None,
                simulado: bool = False, llm=None, memoria_db: Path | None = None,
                user_id: str = "usuario-demo", mensaje_actual: str = "") -> AgentExecutor:
    llm = llm or ChatOpenAI(model=model)

    def buscar_herramienta(texto: str) -> str:
        """Busca productos por nombre o modelo en el catálogo activo."""
        return buscar_productos(catalogo, texto).model_dump_json()

    def catalogo_herramienta(producto_id: str) -> str:
        """Lee ofertas de un producto en el catálogo activo."""
        return text_to_query(catalogo, f"ofertas {producto_id}").model_dump_json()

    def comparar_herramienta(producto_id: str, cantidad: int,
                             presupuesto_centavos: int, plazo_max_dias: int) -> str:
        """Calcula todos los totales, restricciones y motivos de descarte."""
        solicitud = SolicitudCompra(producto_id=producto_id, cantidad=cantidad,
            presupuesto_centavos=presupuesto_centavos, plazo_max_dias=plazo_max_dias)
        return comparar(catalogo, solicitud).model_dump_json()

    def politicas_herramienta(pregunta: str) -> str:
        """Recupera fragmentos del índice FAISS preconstruido."""
        return consultar_politicas(indice, pregunta).model_dump_json()

    def cep_herramienta(cep: str) -> str:
        """Confirma ciudad y UF; no calcula flete ni plazo."""
        return consultar_cep(cep, simulado=simulado).model_dump_json()

    def preferencia_herramienta(clave: str, valor: str, cita_usuario: str) -> str:
        """Guarda una preferencia expresamente pedida en el mensaje actual."""
        if (memoria_db is None or not cita_usuario.strip() or
            cita_usuario not in mensaje_actual or
            not re.search(r"\b(prefiero|preferencia|guarda|recuerda)\b", cita_usuario, re.I) or
            valor.lower() not in cita_usuario.lower()):
            return json.dumps({"estado": "invalido", "error": "sin petición explícita"})
        guardar_preferencia(memoria_db, user_id, clave, valor, explicita=True)
        return json.dumps({"estado": "ok", "clave": clave, "valor": valor})

    herramientas = [StructuredTool.from_function(buscar_herramienta, name="buscar_productos"),
                    StructuredTool.from_function(catalogo_herramienta, name="consultar_catalogo"),
                    StructuredTool.from_function(comparar_herramienta, name="comparar_ofertas"),
                    StructuredTool.from_function(politicas_herramienta, name="consultar_politicas"),
                    StructuredTool.from_function(cep_herramienta, name="consultar_cep"),
                    StructuredTool.from_function(preferencia_herramienta, name="guardar_preferencia")]
    parser = PydanticOutputParser(pydantic_object=RespuestaCompra)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Persona: asistente de compras ficticias. Task: entender, aclarar, consultar, "
                   "comparar y explicar. Context: catálogo activo {dataset_id}, políticas y memoria; "
                   "el requisito actual prevalece sobre preferencias. Format: RespuestaCompra JSON. "
                   "Pide aclaración si falta información o hay ambigüedad. No inventes fuentes. "
                   "Ejemplos de conducta ajenos a evaluación: {ejemplos} "
                   "{format_instructions}"),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ]).partial(dataset_id=catalogo.dataset_id,
               ejemplos=EJEMPLOS_TEXTO,
               format_instructions=parser.get_format_instructions())
    agente = create_openai_tools_agent(llm, herramientas, prompt)
    return AgentExecutor(agent=agente, tools=herramientas, return_intermediate_steps=True,
                         max_iterations=6, handle_parsing_errors=False)


def renderizar(respuesta: RespuestaCompra) -> str:
    """Genera respuesta solo con datos estructurados ya comprobados."""
    if respuesta.estado == "aclaracion":
        faltan = respuesta.solicitud.faltantes()
        return ("Necesito estos datos: " + ", ".join(faltan) + ".") if faltan else "¿Qué producto o modelo específico desea?"
    if respuesta.estado == "sin_oferta":
        lineas = ["Ninguna oferta del catálogo activo cumple simultáneamente stock, presupuesto y plazo."]
        lineas.extend(f"{a.oferta.proveedor_nombre}: {formatar_brl(a.total_centavos)}, "
                      f"descartada por {', '.join(a.motivos)}."
                      for a in respuesta.alternativas)
        return "\n".join(lineas)
    if respuesta.estado == "sin_evidencia":
        return "No puedo confirmar la respuesta con las evidencias disponibles."
    ganadora = next(a for a in respuesta.alternativas
                    if a.oferta.proveedor_id == respuesta.proveedor_id)
    lineas = [f"{ganadora.oferta.proveedor_nombre}: {formatar_brl(ganadora.total_centavos)} "
              f"para {respuesta.solicitud.cantidad} unidades, plazo {ganadora.oferta.plazo_dias} días."]
    lineas.extend(f"{a.oferta.proveedor_nombre}: {formatar_brl(a.total_centavos)}; "
                  f"{'cumple' if a.cumple else ', '.join(a.motivos)}"
                  for a in respuesta.alternativas if a.oferta.id != ganadora.oferta.id)
    lineas.append("Fuentes: " + ", ".join(e.fuente_id for e in respuesta.evidencias))
    return "\n".join(lineas)


def crear_integrador(executor: AgentExecutor, catalogo: Catalogo, memoria_db: Path,
                     *, nli: Callable[[RespuestaCompra], bool] | None = None):
    """Persiste solo la respuesta final; dos propuestas como máximo por turno."""
    parser = PydanticOutputParser(pydantic_object=RespuestaCompra)

    def turno(dato: dict, config: dict) -> AIMessage:
        errores = []
        usuario = config.get("configurable", {}).get("user_id", "")
        sesion = config.get("configurable", {}).get("session_id", "")
        preferencias_usuario = preferencias(memoria_db, usuario) if usuario else {}
        episodios = recuperar_episodios(memoria_db, usuario, dato["input"], k=3) if usuario else []
        contexto = "\n".join(f"Histórico {e['dataset_id']}: {e['texto']}"
                             for e in episodios if e["similitud"] > 0)
        for intento in range(2):
            entrada = dato["input"] if intento == 0 else dato["input"] + "\nCorrige: " + "; ".join(errores)
            if contexto:
                entrada += "\nRecuerdos históricos (precios y stock no vigentes): " + contexto
            if preferencias_usuario:
                entrada += "\nPreferencias guardadas, subordinadas al mensaje actual: " + str(preferencias_usuario)
            try:
                salida = executor.invoke({"input": entrada, "chat_history": dato["chat_history"]},
                    config={"tags": ["compraslab", f"propuesta-{intento + 1}"],
                            "metadata": {"dataset_id": catalogo.dataset_id,
                                         "session_id": sesion, "user_id": usuario}})
                propuesta = parser.parse(salida["output"])
                resultado = verificar(propuesta, catalogo)
                errores = resultado.errores
                if resultado.aprobado and propuesta.estado != "recomendacion":
                    texto = renderizar(propuesta)
                    if usuario and sesion and propuesta.estado == "sin_oferta":
                        guardar_episodio(memoria_db, usuario, sesion, catalogo.dataset_id,
                                         dato["input"] + " | " + texto)
                    return AIMessage(content=texto)
                if resultado.aprobado and nli is not None and nli(propuesta):
                    texto = renderizar(propuesta)
                    if usuario and sesion:
                        guardar_episodio(memoria_db, usuario, sesion, catalogo.dataset_id,
                                         dato["input"] + " | " + texto)
                    return AIMessage(content=texto)
                errores.append("NLI ausente o sin respaldo")
            except Exception as exc:
                errores = [type(exc).__name__]
        return AIMessage(content="No puedo confirmar una recomendación con las evidencias disponibles.")

    return RunnableWithMessageHistory(RunnableLambda(turno),
        lambda user_id, session_id: HistorialSQLite(memoria_db, session_id, user_id),
        input_messages_key="input", history_messages_key="chat_history",
        history_factory_config=[ConfigurableFieldSpec(id="user_id", annotation=str, name="usuario"),
                                ConfigurableFieldSpec(id="session_id", annotation=str, name="sesión")])
