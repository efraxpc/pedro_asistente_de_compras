"""Único flujo de publicación para UI, pruebas y evaluación."""
import json
import re
from pathlib import Path

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import ConfigurableFieldSpec, RunnableLambda, RunnableWithMessageHistory
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import StructuredTool

from .business import brl
from .catalog import Escenario, buscar, ficha, listar, ofertas
from .contracts import RespuestaCompra, Solicitud
from .integrations import consultar_cep
from .memory import (FastEmbedder, Historial, dataset_sesion, guardar_episodio,
                     guardar_preferencia, preferencias, recuperar, tiene_episodios)
from .nli import Clasificador, verificar_nli
from .prompts import EJEMPLOS_ACCIONES
from .query import ejecutar, planear
from .rag import consultar
from .verification import verificar


class Traza(BaseCallbackHandler):
    def __init__(self):
        self.eventos: list[dict] = []

    @staticmethod
    def _seguro(valor: str) -> str:
        return re.sub(r"\b(?:sk|lsv2|lsat)_[A-Za-z0-9_-]{12,}\b|\bsk-[A-Za-z0-9_-]{12,}\b",
                      "[CLAVE OMITIDA]", valor)[:2000]

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        nombre = serialized.get("name")
        self.eventos.append({"evento": "tool_start", "ruta": nombre, "herramienta": nombre,
                             "entrada": self._seguro(input_str)[:1000]})

    def on_tool_end(self, output, **kwargs) -> None:
        resultado = self._seguro(str(output))
        try:
            dato = json.loads(str(output))
            fuentes = [e.get("fuente_id") for e in dato.get("evidencias", [])]
        except (ValueError, AttributeError, TypeError):
            fuentes = []
        self.eventos.append({"evento": "tool_end", "resultado": resultado,
                             "fuentes": [f for f in fuentes if f]})

    def on_tool_error(self, error, **kwargs) -> None:
        self.eventos.append({"evento": "tool_error", "tipo": type(error).__name__})

    def on_chain_error(self, error, **kwargs) -> None:
        self.eventos.append({"evento": "chain_error", "tipo": type(error).__name__})


def herramientas(escenario: Escenario, memoria_db: Path, user_id: str,
                 mensaje_actual: str, indice=None, *, cep_simulado: bool = False):
    def buscar_productos(texto: str) -> str:
        """Busca candidatos por ID, SKU o nombre en el escenario activo."""
        return json.dumps({"dataset_id": escenario.dataset_id, "candidatos": buscar(escenario, texto)}, ensure_ascii=False)

    def consultar_catalogo(pregunta: str) -> str:
        """Consulta ficha u ofertas mediante plan SQL tipado y auditable."""
        return json.dumps(ejecutar(escenario, pregunta, planear(pregunta)), ensure_ascii=False)

    def comparar_ofertas(producto_id: str, cantidad: int, presupuesto_centavos: int,
                         plazo_max_dias: int) -> str:
        """Calcula todas las ofertas y sus descartes exactos en centavos."""
        from .verification import respuesta_local
        solicitud = Solicitud(producto_id=producto_id, cantidad=cantidad,
                             presupuesto_centavos=presupuesto_centavos,
                             plazo_max_dias=plazo_max_dias)
        return respuesta_local(escenario, solicitud).model_dump_json()

    def consultar_politicas(pregunta: str) -> str:
        """Recupera fragmentos de políticas autorizadas, si hay índice."""
        return json.dumps({"fragmentos": consultar(indice, pregunta),
                           "estado": "ok" if indice is not None else "indisponible"}, ensure_ascii=False)

    def consultar_cep_herramienta(cep: str) -> str:
        """Confirma ciudad y UF con ViaCEP; no calcula flete."""
        return json.dumps(consultar_cep(cep, simulado=cep_simulado), ensure_ascii=False)

    def guardar_preferencia_herramienta(clave: str, valor: str, cita_usuario: str) -> str:
        """Guarda solo preferencias citadas explícitamente por el usuario actual."""
        valida = (cita_usuario in mensaje_actual and valor.lower() in cita_usuario.lower() and
                  bool(re.search(r"\b(prefiero|guarda|recuerda|preferencia)\b", cita_usuario, re.I)))
        if not valida:
            return json.dumps({"estado": "invalido", "error": "sin petición explícita"})
        guardar_preferencia(memoria_db, user_id, clave, valor, explicita=True)
        return json.dumps({"estado": "ok", "clave": clave, "valor": valor})

    return [StructuredTool.from_function(buscar_productos, name="buscar_productos"),
            StructuredTool.from_function(consultar_catalogo, name="consultar_catalogo"),
            StructuredTool.from_function(comparar_ofertas, name="comparar_ofertas"),
            StructuredTool.from_function(consultar_politicas, name="consultar_politicas"),
            StructuredTool.from_function(consultar_cep_herramienta, name="consultar_cep"),
            StructuredTool.from_function(guardar_preferencia_herramienta, name="guardar_preferencia")]


def crear_agente(escenario: Escenario, memoria_db: Path, user_id: str,
                mensaje_actual: str, llm, indice=None, *, cep_simulado: bool = False) -> AgentExecutor:
    parser = PydanticOutputParser(pydantic_object=RespuestaCompra)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Persona: Pedro, asistente de compras ficticias. "
         "Tarea: aclara datos, consulta herramientas y compara ofertas del dataset {dataset_id}. "
         "Contexto: los mensajes anteriores y recuerdos son históricos; la solicitud actual prevalece. "
         "Formato: JSON RespuestaCompra válido. No inventes datos ni fuentes. "
         "Plan visible: usa buscar_productos para resolver ID, consultar_catalogo para ofertas y "
         "comparar_ofertas para todos los importes. Una política sin fragmento implica sin_evidencia. "
         "Para políticas usa estado=politica solo con fragmento y fuente_id del índice; "
         "para CEP usa estado=cep con cidade, uf, modo_cep y evidencia ViaCEP. "
         "Si dos piezas coinciden, pide el ID. Ejemplos de acciones observables: "
         "{ejemplos} {formato}"),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")
    ]).partial(dataset_id=escenario.dataset_id, ejemplos=EJEMPLOS_ACCIONES,
               formato=parser.get_format_instructions())
    lista = herramientas(escenario, memoria_db, user_id, mensaje_actual, indice,
                         cep_simulado=cep_simulado)
    return AgentExecutor(agent=create_openai_tools_agent(llm, lista, prompt), tools=lista,
                         return_intermediate_steps=True, max_iterations=6)


def renderizar(respuesta: RespuestaCompra) -> str:
    if respuesta.estado == "aclaracion":
        return "Necesito: " + ", ".join(respuesta.solicitud.faltantes()) if respuesta.solicitud.faltantes() else "Indique el ID exacto de la pieza."
    if respuesta.estado == "sin_evidencia":
        return "No puedo confirmar la respuesta con las fuentes disponibles."
    if respuesta.estado == "cep":
        return (f"CEP {respuesta.solicitud.cep}: {respuesta.cidade}/{respuesta.uf} "
                f"(ViaCEP, modo {respuesta.modo_cep}).")
    if respuesta.estado == "politica":
        return respuesta.mensaje + "\nFuentes: " + ", ".join(
            e.fuente_id for e in respuesta.evidencias if e.tipo == "politica")
    if respuesta.estado == "sin_oferta":
        inicio = "Ninguna oferta cumple stock, presupuesto y plazo."
    else:
        ganadora = next(a for a in respuesta.alternativas if a.oferta.proveedor_id == respuesta.proveedor_id)
        inicio = (f"{ganadora.oferta.proveedor_nombre}: {brl(ganadora.total_centavos)} "
                  f"para {respuesta.solicitud.cantidad} unidades; plazo {ganadora.oferta.plazo_dias} días.")
    lineas = [inicio]
    for a in respuesta.alternativas:
        lineas.append(f"- {a.oferta.proveedor_nombre}: {brl(a.total_centavos)}; "
                      f"{'cumple' if a.cumple else 'descartada por ' + ', '.join(a.motivos)} "
                      f"[{a.oferta.id}]")
    lineas.append("Fuentes: " + ", ".join(e.fuente_id for e in respuesta.evidencias))
    return "\n".join(lineas)


def consulta_directa(escenario: Escenario, pregunta: str) -> str | None:
    texto = pregunta.lower()
    ids = re.findall(r"\bPEC-[0-9]{2}-[0-9]{4}\b", pregunta.upper())
    if re.search(r"\b(ficha|detalle|compatibilidad)\b", texto) and len(set(ids)) == 1:
        dato = ficha(escenario, ids[0])
        if dato is None:
            return "Pieza no encontrada."
        return (f"{dato['name']} ({dato['id']}, SKU {dato['sku']}). {dato['description']} "
                f"Compatibilidad ficticia: " + ", ".join(
                    f"{c['brand']} {c['model_code']}" for c in dato["compatibility"]))
    if (re.search(r"\b(lista|listar|muestra|muéstrame|catalogo|catálogo)\b", texto)
            and re.search(r"\b(piezas|repuestos|catalogo|catálogo)\b", texto)
            and not re.search(r"\b(oferta|precio|stock|comparar)\b", texto)):
        pagina = re.search(r"p[aá]gina\s+(\d+)", texto)
        numero = int(pagina.group(1)) if pagina else 1
        total, piezas = listar(escenario, numero)
        return f"Piezas del escenario ({total}; página {numero}):\n" + "\n".join(
            f"- {p['id']} · {p['sku']} · {p['name']}" for p in piezas)
    return None


def crear_flujo(escenario: Escenario, memoria_db: Path, *, llm=None,
               clasificador: Clasificador | None = None, indice=None,
               cep_simulado: bool = False, traza: Traza | None = None):
    parser = PydanticOutputParser(pydantic_object=RespuestaCompra)

    def turno(dato: dict, config: RunnableConfig) -> AIMessage:
        usuario = config["configurable"]["user_id"]
        sesion = config["configurable"]["session_id"]
        if dataset_sesion(memoria_db, usuario, sesion) != escenario.dataset_id:
            raise ValueError("dataset de sesión distinto del escenario")
        pregunta = dato["input"]
        directa = consulta_directa(escenario, pregunta)
        if directa is not None:
            return AIMessage(content=directa)
        if llm is None:
            return AIMessage(content="Use Comparación local o configure OPENAI_API_KEY para el agente.")
        recuerdos = []
        if tiene_episodios(memoria_db, usuario):
            try:
                recuerdos = recuperar(memoria_db, usuario, pregunta, FastEmbedder())
            except Exception:
                pass
        contexto = "\n".join(f"Recuerdo histórico ({r['dataset_id']}): {r['texto']}" for r in recuerdos)
        pref = preferencias(memoria_db, usuario)
        errores = []
        for intento in range(2):
            entrada = pregunta
            if contexto:
                entrada += "\n" + contexto + "\nNo uses precios o stock históricos."
            if pref:
                entrada += "\nPreferencias subordinadas a la petición actual: " + json.dumps(pref)
            if errores:
                entrada += "\nCorrige estos errores observables: " + "; ".join(errores)
            executor = crear_agente(escenario, memoria_db, usuario, pregunta, llm, indice,
                                    cep_simulado=cep_simulado)
            try:
                salida = executor.invoke({"input": entrada, "chat_history": dato["chat_history"]},
                    config={"callbacks": [traza] if traza else [],
                            "metadata": {"dataset_id": escenario.dataset_id, "user_id": usuario,
                                         "session_id": sesion, "propuesta": intento + 1}})
                propuesta = parser.parse(salida["output"])
                observaciones = []
                for accion, resultado_tool in salida.get("intermediate_steps", []):
                    try:
                        observaciones.append((accion.tool, json.loads(str(resultado_tool))))
                    except (ValueError, TypeError, AttributeError):
                        pass
                errores = verificar(propuesta, escenario, indice=indice,
                                    observaciones=observaciones)
                if not errores and propuesta.estado in ("recomendacion", "politica"):
                    if clasificador is None or not verificar_nli(propuesta, clasificador):
                        errores = ["NLI sin entailment"]
                if not errores:
                    texto = renderizar(propuesta)
                    if propuesta.estado in ("recomendacion", "sin_oferta"):
                        try:
                            guardar_episodio(memoria_db, usuario, sesion, pregunta + " | " + texto,
                                             FastEmbedder())
                        except Exception:
                            pass
                    return AIMessage(content=texto)
            except Exception as exc:
                errores = [type(exc).__name__]
        return AIMessage(content="No puedo confirmar una recomendación con las evidencias disponibles.")

    return RunnableWithMessageHistory(RunnableLambda(turno),
        lambda user_id, session_id: Historial(memoria_db, user_id, session_id),
        input_messages_key="input", history_messages_key="chat_history",
        history_factory_config=[ConfigurableFieldSpec(id="user_id", annotation=str, name="usuario"),
                                ConfigurableFieldSpec(id="session_id", annotation=str, name="sesión")])
