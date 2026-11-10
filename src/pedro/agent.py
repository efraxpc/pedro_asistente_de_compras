"""Único flujo de publicación para UI, pruebas y evaluación."""
import json
import re
from pathlib import Path

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import ConfigurableFieldSpec, RunnableLambda, RunnableWithMessageHistory
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import StructuredTool

from .business import brl
from .catalog import Escenario, buscar, ficha, listar, ofertas
from .contracts import Evidencia, RespuestaCompra, Solicitud
from .dialogue import EstadoCompra, interpretar_compra
from .integrations import consultar_cep
from .memory import (FastEmbedder, Historial, dataset_sesion, guardar_borrador,
                     guardar_episodio, guardar_preferencia, leer_borrador,
                     preferencias, recuperar, tiene_episodios)
from .nli import Clasificador, verificar_nli
from .policy_demo import (FRAGMENTO_T24_ESPERADO, ORIGEN as ORIGEN_DEMO,
                          PREGUNTA_T24_ORIGINAL, PREGUNTA_T24_REESCRITA,
                          reescribir_consulta_entrega)
from .prompts import EJEMPLOS_ACCIONES, PLANTILLA_AGENTE
from .query import ejecutar, planear
from .rag import consultar, diagnosticar_reescritura
from .verification import anclar_citas, respuesta_local, verificar


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

    def registrar_citas(self, citas: list[dict]) -> None:
        if citas:
            self.eventos.append({"evento": "citas_ancladas", "citas": citas})

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

    def comparar_ofertas(producto_id: str, cantidad: int,
                         presupuesto_centavos: int | None = None,
                         plazo_max_dias: int | None = None) -> str:
        """Calcula todas las ofertas y sus descartes exactos en centavos."""
        from .verification import respuesta_local
        solicitud = Solicitud(producto_id=producto_id, cantidad=cantidad,
                             presupuesto_centavos=presupuesto_centavos,
                             plazo_max_dias=plazo_max_dias)
        return respuesta_local(escenario, solicitud).model_dump_json()

    def consultar_politicas(pregunta: str) -> str:
        """Recupera políticas, incluida la entrega en varias cajas, con fuentes."""
        reescrita = reescribir_consulta_entrega(pregunta)
        diagnostico = None
        if indice is not None and reescrita is not None:
            referencia = indice.docstore.search(FRAGMENTO_T24_ESPERADO)
            if getattr(referencia, "metadata", {}).get("origen") == ORIGEN_DEMO:
                informe = diagnosticar_reescritura(
                    indice, pregunta, reescrita, FRAGMENTO_T24_ESPERADO, k=4)
                fragmentos = informe["despues"]
                diagnostico = {
                    "metrica": informe["metrica"], "k": informe["k"],
                    "fuente_esperada": FRAGMENTO_T24_ESPERADO,
                    "posicion_antes": informe["posicion_antes"],
                    "posicion_despues": informe["posicion_despues"],
                    "correccion_observada": informe["correccion_observada"],
                    "antes": [{"fuente_id": r["fuente_id"], "score": r["score"]}
                              for r in informe["antes"]],
                    "despues": [{"fuente_id": r["fuente_id"], "score": r["score"]}
                                for r in informe["despues"]],
                }
            else:
                import faiss

                antes = consultar(indice, pregunta)
                fragmentos = consultar(indice, reescrita)
                diagnostico = {
                    "metrica": "L2" if indice.index.metric_type == faiss.METRIC_L2 else "IP",
                    "k": 4,
                    "antes": [{"fuente_id": r["fuente_id"], "score": r["score"]}
                              for r in antes],
                    "despues": [{"fuente_id": r["fuente_id"], "score": r["score"]}
                                for r in fragmentos],
                }
        else:
            fragmentos = consultar(indice, pregunta)
        return json.dumps({
            "fragmentos": fragmentos,
            "estado": "ok" if fragmentos else
                      "sin_evidencia" if indice is not None else "indisponible",
            "consulta_original": pregunta,
            "consulta_reescrita": reescrita,
            "diagnostico": diagnostico,
        }, ensure_ascii=False)

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
    prompt = PLANTILLA_AGENTE.partial(dataset_id=escenario.dataset_id, ejemplos=EJEMPLOS_ACCIONES,
                                      formato=parser.get_format_instructions())
    lista = herramientas(escenario, memoria_db, user_id, mensaje_actual, indice,
                         cep_simulado=cep_simulado)
    return AgentExecutor(agent=create_openai_tools_agent(llm, lista, prompt), tools=lista,
                         return_intermediate_steps=True, max_iterations=6)


def renderizar(respuesta: RespuestaCompra, *, indice=None) -> str:
    if respuesta.estado == "aclaracion":
        if not (respuesta.solicitud.producto_id or respuesta.solicitud.producto):
            return "¿Qué pieza necesitas? Indica su ID o SKU."
        if respuesta.solicitud.cantidad is None:
            return "¿Cuántas unidades necesitas?"
        return "¿Cuál es el ID exacto de la pieza?"
    if respuesta.estado == "sin_evidencia":
        return "No puedo confirmar la respuesta con las fuentes disponibles."
    if respuesta.estado == "cep":
        return (f"CEP {respuesta.solicitud.cep}: {respuesta.cidade}/{respuesta.uf} "
                f"(ViaCEP, modo {respuesta.modo_cep}).")
    if respuesta.estado == "politica":
        ficticia = indice is not None and any(
            getattr(indice.docstore.search(e.fuente_id), "metadata", {}).get("origen") == ORIGEN_DEMO
            for e in respuesta.evidencias if e.tipo == "politica")
        prefijo = "Política ficticia de demostración. " if ficticia else ""
        return prefijo + respuesta.mensaje + "\nFuentes: " + ", ".join(
            e.fuente_id for e in respuesta.evidencias if e.tipo == "politica")
    if respuesta.estado == "sin_oferta":
        inicio = "Ninguna oferta cumple las restricciones indicadas."
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


def renderizar_citas(respuesta: RespuestaCompra, *, indice=None) -> str:
    """Respuesta extractiva: solo texto literal de las fuentes, sin resumen del modelo."""
    citas = [e for e in respuesta.evidencias if e.tipo == "politica"]
    ficticia = indice is not None and any(
        getattr(indice.docstore.search(e.fuente_id), "metadata", {}).get("origen") == ORIGEN_DEMO
        for e in citas)
    prefijo = "Política ficticia de demostración. " if ficticia else ""
    return (prefijo + "No pude verificar un resumen propio, así que cito el texto literal "
            "de la fuente:\n" + "\n".join(f"- «{e.texto}» [{e.fuente_id}]" for e in citas))


def es_diagnostico_t24(pregunta: str) -> bool:
    """Reconoce el comando de demostración controlada del chat."""
    return pregunta.strip().casefold() in {"/t24", "t24", "prueba t24"}


def resumen_recuperacion_t24(diagnostico: dict | None) -> str:
    """Describe un contraste observado por la herramienta, sin inferencia del LLM."""
    if not diagnostico or not diagnostico.get("correccion_observada"):
        return ""
    return (
        f"Recuperación T24: la pregunta inicial dejó "
        f"`{diagnostico['fuente_esperada']}` fuera del top-{diagnostico['k']}; "
        f"la reformulación lo situó en la posición "
        f"{diagnostico['posicion_despues']} con el mismo índice y top-k."
    )


def resolver_entrega_parcial(escenario: Escenario, memoria_db: Path, usuario: str,
                            pregunta: str, indice, clasificador: Clasificador | None,
                            traza: Traza | None = None) -> str | None:
    """Ruta extractiva verificada para preguntas de envío dividido del corpus demo."""
    if indice is None or reescribir_consulta_entrega(pregunta) is None:
        return None
    referencia = indice.docstore.search(FRAGMENTO_T24_ESPERADO)
    if getattr(referencia, "metadata", {}).get("origen") != ORIGEN_DEMO:
        return None
    herramienta = next(h for h in herramientas(escenario, memoria_db, usuario,
                                               pregunta, indice)
                       if h.name == "consultar_politicas")
    try:
        resultado_tool = herramienta.invoke(
            {"pregunta": pregunta}, config={"callbacks": [traza] if traza else []})
        dato_tool = json.loads(resultado_tool)
    except Exception:
        return "No pude consultar las políticas ficticias para esta pregunta."
    diagnostico = dato_tool.get("diagnostico")
    if not diagnostico or not diagnostico.get("correccion_observada"):
        return "No pude confirmar una recuperación corregida para esta pregunta."
    fragmento = next((f for f in dato_tool.get("fragmentos", [])
                      if f.get("fuente_id") == FRAGMENTO_T24_ESPERADO), None)
    if fragmento is None:
        return "La reformulación no recuperó la regla de entrega parcial."
    fuente = fragmento["texto"]
    frases = [coincidencia.group(0) for patron in (
        r"Una entrega parcial[^.]*\.", r"Si no existe ese acuerdo[^.]*\.")
        if (coincidencia := re.search(patron, fuente))]
    if len(frases) != 2:
        return "El fragmento recuperado no contiene la regla completa de entrega parcial."
    respuesta = RespuestaCompra(
        estado="politica", dataset_id=escenario.dataset_id, solicitud=Solicitud(),
        mensaje=" ".join(frases),
        evidencias=[Evidencia(tipo="politica", fuente_id=FRAGMENTO_T24_ESPERADO,
                             texto=fuente)],
    )
    if verificar(respuesta, escenario, indice=indice,
                observaciones=[("consultar_politicas", dato_tool)]):
        return "Encontré la regla, pero no pude verificar su fuente en el índice."
    if clasificador is None or not verificar_nli(respuesta, clasificador):
        return ("Encontré el fragmento de entrega parcial, pero no pude verificar "
                "la respuesta con NLI local; no confirmo la regla.")
    return renderizar(respuesta, indice=indice) + "\n\n" + resumen_recuperacion_t24(diagnostico)


def renderizar_diagnostico_t24(indice) -> str:
    """Muestra la misma comparación reproducible del notebook, sin LLM."""
    if indice is None:
        return "No se pudo cargar el índice ficticio necesario para la prueba T24."
    try:
        informe = diagnosticar_reescritura(
            indice, PREGUNTA_T24_ORIGINAL, PREGUNTA_T24_REESCRITA,
            FRAGMENTO_T24_ESPERADO, k=4)
    except ValueError:
        return "La prueba T24 requiere el corpus ficticio de políticas de demostración."

    introduccion = [
        "### Prueba T24 · recuperación ficticia",
        f"Pregunta inicial: {PREGUNTA_T24_ORIGINAL}",
        f"Reformulación: {PREGUNTA_T24_REESCRITA}",
        f"Índice: {informe['total_fragmentos']} fragmentos; métrica {informe['metrica']}; "
        f"top-{informe['k']} en ambas búsquedas.",
    ]
    tabla = [
        "| Consulta | Posición | Fragmento | Fuente / sección | Distancia L2 |",
        "|---|---:|---|---|---:|",
    ]
    for etapa, etiqueta in (("antes", "Inicial"), ("despues", "Reformulada")):
        for resultado in informe[etapa]:
            meta = resultado["metadatos"]
            tabla.append(
                f"| {etiqueta} | {resultado['posicion']} | `{resultado['fuente_id']}` | "
                f"{meta.get('fuente', '?')} / {meta.get('seccion', '?')} | "
                f"{resultado['score']:.3f} |"
            )
    posicion_antes = informe["posicion_antes"] or "fuera del top-4"
    posicion_despues = informe["posicion_despues"] or "fuera del top-4"
    detalles = [
        f"Fragmento esperado `{FRAGMENTO_T24_ESPERADO}`: antes {posicion_antes}; "
        f"después {posicion_despues}. "
        "Fuente: entrega.md, sección «Entrega parcial y stock». "
        "En L2, una distancia menor indica mayor cercanía."
    ]
    regla = re.search(r"Una entrega parcial[^.]*\.",
                      informe["evidencia_esperada"]["texto"])
    if regla:
        detalles.append(f"Regla en el fragmento fuente: «{regla.group(0)}»")
    filtrados = consultar(indice, PREGUNTA_T24_ORIGINAL, k=4,
                         filtro={"tema": "entrega"}, fetch_k=indice.index.ntotal)
    posicion_filtro = next((r["posicion"] for r in filtrados
                           if r["fuente_id"] == FRAGMENTO_T24_ESPERADO), None)
    detalles.append(
        f"Prueba separada con filtro `tema=entrega`: fragmento esperado en posición "
        f"{posicion_filtro if posicion_filtro is not None else 'fuera del top-4'}."
    )
    if not informe["correccion_observada"]:
        detalles.append("La corrección ya no se reproduce con este índice; revise el corpus y el modelo.")
    detalles.append("Demostración sintética: falta repetirla en el índice preexistente para R22/R23.")
    return "\n\n".join(introduccion + ["\n".join(tabla)] + detalles)


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
        if es_diagnostico_t24(pregunta):
            return AIMessage(content=renderizar_diagnostico_t24(indice))
        if reescribir_consulta_entrega(pregunta) is not None:
            politica = resolver_entrega_parcial(escenario, memoria_db, usuario,
                                                pregunta, indice, clasificador, traza)
            if politica is not None:
                return AIMessage(content=politica)
        directa = consulta_directa(escenario, pregunta)
        if directa is not None:
            return AIMessage(content=directa)
        borrador = leer_borrador(memoria_db, usuario, sesion)
        previo = EstadoCompra.model_validate(borrador) if borrador is not None else None
        compra = interpretar_compra(escenario, previo, pregunta)
        solicitud_actual = None
        if compra is not None:
            estado, aclaracion = compra
            guardar_borrador(memoria_db, usuario, sesion, estado.model_dump())
            if aclaracion is not None:
                return AIMessage(content=aclaracion)
            solicitud_actual = estado.solicitud
            if llm is None:
                propuesta = respuesta_local(escenario, solicitud_actual)
                errores = verificar(propuesta, escenario)
                if errores:
                    return AIMessage(content="No puedo confirmar una recomendación con las evidencias disponibles.")
                return AIMessage(content=renderizar(propuesta))
        if llm is None:
            return AIMessage(content="Puedo comparar piezas aquí. Indica un ID o SKU y la cantidad; para políticas o CEP configura OPENAI_API_KEY.")
        recuerdos = []
        if tiene_episodios(memoria_db, usuario):
            try:
                recuerdos = recuperar(memoria_db, usuario, pregunta, FastEmbedder())
            except Exception:
                pass
        contexto = "\n".join(f"Recuerdo histórico ({r['dataset_id']}): {r['texto']}" for r in recuerdos)
        pref = preferencias(memoria_db, usuario)
        errores = []
        extractiva = None
        for intento in range(2):
            entrada = pregunta
            if solicitud_actual is not None:
                entrada += ("\nSolicitud estructurada vigente (la petición actual ya prevaleció sobre el "
                            "historial; respétala exactamente): " + solicitud_actual.model_dump_json())
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
                citas = anclar_citas(propuesta, observaciones)
                if traza:
                    traza.registrar_citas(citas)
                errores = verificar(propuesta, escenario, indice=indice,
                                    observaciones=observaciones)
                if solicitud_actual is not None and propuesta.estado not in (
                        "recomendacion", "sin_oferta", "sin_evidencia"):
                    errores.append("respuesta ajena a la comparación solicitada")
                if solicitud_actual is not None and propuesta.estado in ("recomendacion", "sin_oferta"):
                    campos = ("producto_id", "cantidad", "presupuesto_centavos", "plazo_max_dias")
                    if any(getattr(propuesta.solicitud, c) != getattr(solicitud_actual, c) for c in campos):
                        errores.append("solicitud distinta de la petición vigente")
                if not errores and propuesta.estado in ("recomendacion", "politica"):
                    if clasificador is None or not verificar_nli(propuesta, clasificador):
                        errores = ["NLI sin entailment"]
                        if propuesta.estado == "politica" and solicitud_actual is None:
                            # Las citas ya son literales y verificadas; solo falló el resumen.
                            extractiva = propuesta
                if not errores:
                    texto = renderizar(propuesta, indice=indice)
                    if propuesta.estado == "politica":
                        fuentes_publicadas = {e.fuente_id for e in propuesta.evidencias
                                               if e.tipo == "politica"}
                        for nombre, dato_tool in observaciones:
                            diagnostico = dato_tool.get("diagnostico") if nombre == "consultar_politicas" else None
                            if (diagnostico and diagnostico.get("correccion_observada") and
                                    diagnostico.get("fuente_esperada") in fuentes_publicadas):
                                texto += "\n\n" + resumen_recuperacion_t24(diagnostico)
                                break
                    if propuesta.estado in ("recomendacion", "sin_oferta"):
                        try:
                            guardar_episodio(memoria_db, usuario, sesion, pregunta + " | " + texto,
                                             FastEmbedder())
                        except Exception:
                            pass
                    return AIMessage(content=texto)
            except Exception as exc:
                errores = [type(exc).__name__]
        if extractiva is not None:
            return AIMessage(content=renderizar_citas(extractiva, indice=indice))
        if indice is not None and re.search(r"\b(pol[ií]tica|entrega|devoluci[oó]n|garant[ií]a)\b",
                                            pregunta, re.I):
            return AIMessage(content="No pude verificar la respuesta sobre políticas. "
                                     "Puedes reformular la pregunta o escribir /t24 para "
                                     "ver el diagnóstico de recuperación.")
        return AIMessage(content="No puedo confirmar una recomendación con las evidencias disponibles.")

    return RunnableWithMessageHistory(RunnableLambda(turno),
        lambda user_id, session_id: Historial(memoria_db, user_id, session_id),
        input_messages_key="input", history_messages_key="chat_history",
        history_factory_config=[ConfigurableFieldSpec(id="user_id", annotation=str, name="usuario"),
                                ConfigurableFieldSpec(id="session_id", annotation=str, name="sesión")])
