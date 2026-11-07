"""Agente clásico y publicación posterior a verificación; requiere modelo configurado."""
from pathlib import Path
from typing import Callable
import json
import re
import unicodedata

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import ConfigurableFieldSpec, RunnableLambda, RunnableWithMessageHistory
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI

from .data import Catalogo, listar_productos
from .part_catalog import detalle_pieza, listar_piezas
from .business import formatar_brl
from .integrations import consultar_cep
from .memory import (HistorialSQLite, guardar_episodio, guardar_preferencia,
                     preferencias, recuperar_episodios)
from .query import text_to_query
from .prompts import EJEMPLOS_TEXTO
from .schemas import RespuestaCompra, SolicitudCompra
from .tools import buscar_productos, comparar, consultar_politicas
from .verification import verificar


def responder_consulta_catalogo(catalogo: Catalogo, pregunta: str) -> str | None:
    """Answer catalog browsing questions from the active, verified snapshot."""
    texto = "".join(c for c in unicodedata.normalize("NFKD", pregunta.lower())
                    if not unicodedata.combining(c))
    if (re.search(r"\b(fuente|origen|de donde)\b", texto) and
            re.search(r"\b(datos?|productos?|catalogo)\b", texto)):
        return ("Este escenario usa la base SQLite local de piezas ficticias de "
                "electrodomésticos. Los proveedores, compatibilidades, existencias, "
                "precios y conversiones a BRL son simulados.")
    if re.search(
            r"\b(detalle|detalles|ficha|informacion|datos|compatibilidad|proveedores|ofertas)\b", texto):
        productos = listar_productos(catalogo)
        producto = next((p for p in productos if p.id.lower() in texto or
                         p.modelo.lower() in pregunta.lower()), None)
        if producto is not None:
            pieza = detalle_pieza(catalogo, producto.modelo)
            if pieza is not None:
                lineas = [f"{pieza['name']} ({pieza['product_id']}, SKU {pieza['sku']})",
                          pieza["description"],
                          f"Categoría: {pieza['category']}; fabricante: {pieza['manufacturer']}; "
                          f"tipo: {pieza['part_kind']}; garantía: {pieza['warranty_months']} meses.",
                          "Compatibilidad ficticia: " + ", ".join(
                              f"{c['brand']} {c['model_code']} ({c['year_from']}–{c['year_to']})"
                              for c in pieza["compatibility"]), "Ofertas ficticias:"]
                lineas.extend(f"- {o['supplier_name']} ({o['country_code']}): "
                              f"{formatar_brl(o['estimated_brl_cents'])}, "
                              f"stock {o['stock_qty']}, plazo {o['lead_days']} días."
                              for o in pieza["offers"])
                lineas.append("Todos los datos técnicos y el historial de precios están en «Catálogo de piezas».")
                return "\n".join(lineas)
    if (re.search(r"\b(productos?|piezas?|catalogo)\b", texto) and
            re.search(r"\b(muestrame|muestra|mostrar|lista|listar|ver|cuales|que|tienes|hay|todas|todos)\b", texto)):
        piezas = listar_piezas(catalogo)
        categorias = {"".join(c for c in unicodedata.normalize("NFKD", p["category"].lower())
                               if not unicodedata.combining(c)): p["category"] for p in piezas}
        categoria = next((nombre for normalizada, nombre in categorias.items()
                          if re.search(rf"\b{re.escape(normalizada)}\b", texto)), None)
        if categoria:
            piezas = [p for p in piezas if p["category"] == categoria]
        pagina_match = re.search(r"\bpagina\s+(\d+)\b", texto)
        pagina = int(pagina_match.group(1)) if pagina_match else 1
        paginas = max(1, (len(piezas) + 19) // 20)
        if pagina < 1 or pagina > paginas:
            return f"Página fuera de rango. Hay {paginas} páginas para esta consulta."
        inicio = (pagina - 1) * 20
        lineas = [f"Piezas del escenario activo ({len(piezas)} en total; página {pagina}/{paginas}):"]
        lineas.extend(f"- {p['name']} ({p['product_id']}, SKU {p['sku']})"
                      for p in piezas[inicio:inicio + 20])
        lineas.append("Pida «página 2» junto con la categoría o abra «Catálogo de piezas» para verlas todas.")
        return "\n".join(lineas)
    return None


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
        ("system", "Persona: Pedro, asistente de compras ficticias. Task: entender, aclarar, consultar, "
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


def crear_integrador(executor: AgentExecutor | None, catalogo: Catalogo, memoria_db: Path,
                     *, nli: Callable[[RespuestaCompra], bool] | None = None):
    """Persiste solo la respuesta final; dos propuestas como máximo por turno."""
    parser = PydanticOutputParser(pydantic_object=RespuestaCompra)

    def turno(dato: dict, config: dict) -> AIMessage:
        respuesta_catalogo = responder_consulta_catalogo(catalogo, dato["input"])
        if respuesta_catalogo is not None:
            return AIMessage(content=respuesta_catalogo)
        if executor is None:
            return AIMessage(content="Configure OPENAI_API_KEY para solicitar recomendaciones al agente.")
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
                    config={"tags": ["pedro-asistente-de-compras", f"propuesta-{intento + 1}"],
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
