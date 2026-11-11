"""Interfaz local: chat y comparación de proveedores de piezas ficticias."""
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pedro.agent import Traza, crear_flujo, es_diagnostico_t24, partes_de
from pedro.business import brl, describir_motivos, variacion_porcentual
from pedro.catalog import abrir_escenario, crear_escenario, ficha
from pedro.contracts import Alternativa, Oferta, RespuestaCompra, Solicitud
from pedro.memory import MODELO_RECUERDOS, Historial, nueva_sesion, sesiones
from pedro.policy_demo import crear_indice_demo, huella_corpus
from pedro.precios import aviso_de_precio
from pedro.verification import mejor_sin_preferencia, respuesta_local, verificar

load_dotenv()
BASE = Path(os.getenv("PEDRO_STORAGE", "storage"))
CATALOGOS = BASE / "catalogos"
MEMORIA = BASE / "memoria.sqlite3"
USUARIO = "usuario-demo"
CONVERSACIONES_VISIBLES = 8
st.set_page_config(page_title="Pedro · asistente de compras", page_icon=":material/shopping_cart:",
                   layout="wide")


@st.cache_resource(show_spinner=False, max_entries=1)
def modelo_nli():
    from pedro.nli import ModeloNLI
    return ModeloNLI()


@st.cache_resource(show_spinner=False, max_entries=2)
def indice_politicas(carpeta: str, huella_contenido: str, modelo: str):
    from pedro.rag import cargar_indice
    if modelo == MODELO_RECUERDOS:
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        embeddings = FastEmbedEmbeddings(model_name=modelo, doc_embed_type="passage")
    else:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(model=modelo)
    return cargar_indice(Path(carpeta), embeddings,
                         origen_confiable=True)[0]


@st.cache_resource(show_spinner=False, max_entries=1)
def indice_politicas_demo(huella_contenido: str):
    return crear_indice_demo()


def nuevo_escenario() -> None:
    st.session_state.escenario = crear_escenario(CATALOGOS)
    st.session_state.sesion = nueva_sesion(MEMORIA, USUARIO, st.session_state.escenario.dataset_id)


def nuevo_chat() -> None:
    st.session_state.sesion = nueva_sesion(MEMORIA, USUARIO, st.session_state.escenario.dataset_id)


def reabrir(session_id: str, dataset_id: str) -> None:
    st.session_state.sesion = session_id
    try:
        st.session_state.escenario = abrir_escenario(CATALOGOS, dataset_id)
        st.session_state.error_escenario = None
    except (FileNotFoundError, ValueError):
        st.session_state.escenario = None
        st.session_state.error_escenario = "El escenario de esta conversación ya no está disponible."


def sugerir(texto: str) -> None:
    st.session_state.sugerida = texto


# --- Presentación de una comparación de proveedores ---------------------------------------

def origen(oferta: Oferta) -> str:
    return "Nacional" if oferta.nacional else "Internacional"


def frente_a_media(oferta: Oferta) -> str:
    if not oferta.precio_medio_centavos:
        return "—"
    puntos = variacion_porcentual(oferta.precio_unitario_centavos, oferta.precio_medio_centavos)
    return "igual" if puntos == 0 else f"{puntos:+d} %"


def tabla_de_ofertas(alternativas: list[Alternativa]) -> None:
    """Todas las ofertas comparadas: quién cumple, quién no y por qué."""
    st.dataframe(
        [{"Proveedor": a.oferta.proveedor_nombre, "Origen": origen(a.oferta),
          "Total": brl(a.total_centavos), "Cumple": a.cumple,
          "Motivo de descarte": describir_motivos(a) or "—",
          "Precio por unidad": brl(a.oferta.precio_unitario_centavos),
          "Frente a su media": frente_a_media(a.oferta),
          "Entrega (días)": a.oferta.plazo_dias, "Pedido mínimo": a.oferta.pedido_minimo,
          "Stock": a.oferta.stock, "Oferta": a.oferta.id} for a in alternativas],
        hide_index=True,
        column_config={
            "Cumple": st.column_config.CheckboxColumn(help="Cumple stock, pedido mínimo, plazo y presupuesto"),
            "Frente a su media": st.column_config.TextColumn(
                help="Precio por unidad de hoy frente a la media de los meses anteriores"),
            "Oferta": st.column_config.TextColumn(help="Identificador de la oferta en el catálogo"),
        },
        alt="Ofertas comparadas, con su total, si cumplen y el motivo de descarte")


def mostrar_comparacion(respuesta: RespuestaCompra, consejo: str | None = None) -> None:
    """Dibuja una comparación verificada: ganador, aviso de precio y todas las ofertas."""
    solicitud = respuesta.solicitud
    if respuesta.estado == "sin_oferta":
        st.warning(f"Ninguna oferta cumple para {solicitud.cantidad} unidades de "
                   f"{solicitud.producto_id}. La tabla muestra por qué se descartó cada una.",
                   title="Sin oferta válida", icon=":material/block:")
    else:
        ganadora = next(a for a in respuesta.alternativas
                        if a.oferta.proveedor_id == respuesta.proveedor_id)
        with st.container(horizontal=True):
            st.metric("Proveedor recomendado", ganadora.oferta.proveedor_nombre, border=True,
                      height="stretch", icon=":material/storefront:")
            st.metric(f"Total por {solicitud.cantidad} unidades", brl(ganadora.total_centavos),
                      border=True, height="stretch", icon=":material/payments:")
            st.metric("Entrega", f"{ganadora.oferta.plazo_dias} días", border=True,
                      height="stretch", icon=":material/local_shipping:")
            st.metric("Origen", origen(ganadora.oferta), border=True, height="stretch",
                      icon=":material/public:")
        if consejo:
            st.info(consejo, title="Consejo sobre el precio · redactado por el modelo y verificado",
                    icon=":material/insights:")
        elif aviso := aviso_de_precio(respuesta):
            st.warning(aviso, title="Aviso de precio", icon=":material/trending_up:")
        if solicitud.origen_preferido:
            nota = f"Se aplicó tu preferencia por proveedores {solicitud.origen_preferido}es."
            barata = mejor_sin_preferencia(respuesta)
            if barata is not None:
                nota += (f" Sin ella, la más barata sería {barata.oferta.proveedor_nombre} "
                         f"por {brl(barata.total_centavos)}.")
            st.info(nota, icon=":material/favorite:")
    tabla_de_ofertas(respuesta.alternativas)
    validas = [a for a in respuesta.alternativas if a.cumple and a.oferta.meses_historial]
    if validas:
        with st.expander("Historial de precios de las ofertas válidas", icon=":material/history:"):
            st.dataframe(
                [{"Proveedor": a.oferta.proveedor_nombre,
                  "Hoy": brl(a.oferta.precio_unitario_centavos),
                  "Mes anterior": brl(a.oferta.precio_anterior_centavos or 0),
                  f"Media de {a.oferta.meses_historial} meses": brl(a.oferta.precio_medio_centavos or 0),
                  "Frente a su media": frente_a_media(a.oferta),
                  "Mínimo del periodo": brl(a.oferta.precio_minimo_centavos or 0),
                  "Máximo del periodo": brl(a.oferta.precio_maximo_centavos or 0)} for a in validas],
                hide_index=True, alt="Historial del precio por unidad de cada oferta válida")
            st.caption("El historial informa: no cambia qué oferta gana.")
    st.caption("Fuentes: " + ", ".join(a.oferta.id for a in respuesta.alternativas))


def mostrar_mensaje(mensaje) -> None:
    """Respuesta del asistente: las comparaciones como tarjetas y tabla, el resto como texto."""
    for parte in partes_de(mensaje):
        if parte.get("titulo"):
            st.markdown(f"**{parte['titulo']}**")
        if parte.get("comparacion"):
            mostrar_comparacion(RespuestaCompra.model_validate(parte["comparacion"]),
                                parte.get("consejo"))
        else:
            st.markdown(parte["texto"])


# --- Pasos del agente ----------------------------------------------------------------------

HERRAMIENTAS = {
    "buscar_productos": "Busqué la pieza en el catálogo",
    "consultar_catalogo": "Consulté el catálogo",
    "comparar_ofertas": "Comparé las ofertas de los proveedores",
    "consultar_politicas": "Busqué en las políticas",
    "consultar_cep": "Consulté el CEP en ViaCEP",
    "guardar_preferencia": "Guardé tu preferencia",
}
ANCLAJES = {"comparacion_anclada": "Tomé las cifras del cálculo de la herramienta",
            "cep_anclado": "Tomé la ciudad de la respuesta de ViaCEP",
            "citas_ancladas": "Comprobé las citas contra el texto de la fuente",
            "catalogo_anclado": "Armé la tabla con las filas de la consulta",
            "preferencia_anclada": "Confirmé lo que se guardó"}


def describir_paso(evento: dict) -> dict | None:
    """Convierte un evento de la traza en un paso legible; None si no merece mostrarse."""
    tipo = evento["evento"]
    if tipo == "plan":
        return {"etiqueta": f"Dividí tu mensaje en {len(evento['peticiones'])} peticiones",
                "detalle": "\n".join(f"- {p['peticion']}" for p in evento["peticiones"])}
    if tipo == "interpretacion":
        lectura = evento.get("modelo") or {}
        if not lectura.get("es_compra"):
            return {"etiqueta": "Leí tu mensaje: no es una compra", "detalle": ""}
        cambios = {k: v for k, v in lectura.items() if k != "es_compra" and v not in (None, [])}
        return {"etiqueta": "Leí tu mensaje",
                "detalle": f"Cambios en la solicitud: `{json.dumps(cambios, ensure_ascii=False)}`"
                if cambios else "Sin cambios en cantidad, presupuesto ni plazo."}
    if tipo == "tool_start":
        return {"etiqueta": HERRAMIENTAS.get(evento["herramienta"], evento["herramienta"]),
                "detalle": f"`{evento['herramienta']}` con `{evento['entrada']}`"}
    if tipo == "verificacion":
        if evento["errores"]:
            return {"etiqueta": "La propuesta no pasó la verificación; pedí otra", "estado": "error",
                    "detalle": "\n".join(f"- {e}" for e in evento["errores"])}
        return {"etiqueta": "Verifiqué la respuesta", "detalle": "Sin errores."}
    if tipo in ANCLAJES:
        return {"etiqueta": ANCLAJES[tipo], "detalle": ""}
    if tipo == "consejo_precio":
        if evento.get("fuente") == "consejo verificado":
            return {"etiqueta": "Redacté un consejo de precio y lo verifiqué", "detalle": ""}
        return {"etiqueta": "Descarté mi consejo de precio; uso el aviso de plantilla", "estado": "error",
                "detalle": "\n".join(f"- {e}" for e in evento.get("errores") or [])}
    return None


def mostrar_paso(paso: dict) -> None:
    with st.status(paso["etiqueta"], type="step", state=paso.get("estado", "complete")):
        if paso.get("detalle"):
            st.markdown(paso["detalle"])


class PasosEnVivo(list):
    """Lista de eventos de la traza que dibuja cada paso en cuanto ocurre."""

    def __init__(self):
        super().__init__()
        self.pasos: list[dict] = []

    def append(self, evento: dict) -> None:
        super().append(evento)
        paso = describir_paso(evento)
        if paso is None:
            return
        self.pasos.append(paso)
        try:
            mostrar_paso(paso)
        except Exception:  # un paso que no se puede dibujar no debe romper la respuesta
            pass


def preparar_agente(prueba_t24: bool):
    """Carga el modelo, el NLI y el índice de políticas disponibles para este turno."""
    llm = clasificador = indice = None
    if os.getenv("OPENAI_API_KEY") and not prueba_t24:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=os.getenv("PEDRO_MODEL", "gpt-4.1-mini"))
        try:
            clasificador = modelo_nli()
        except Exception:
            st.warning("El modelo NLI no está disponible; las recomendaciones quedarán bloqueadas.")
    carpeta = Path("knowledge/politicas")
    if prueba_t24:
        try:
            indice = indice_politicas_demo(huella_corpus())
        except Exception as exc:
            st.warning(f"Prueba T24 no disponible: {type(exc).__name__}")
    elif (carpeta / "manifest.json").is_file() and llm is not None:
        if os.getenv("PEDRO_TRUST_POLICY_INDEX", "false").lower() != "true":
            st.warning("Revise la procedencia del índice antes de habilitar su docstore.")
        else:
            try:
                from pedro.rag import inspeccionar_indice
                meta = inspeccionar_indice(carpeta)
                indice = indice_politicas(str(carpeta), json.dumps(meta["sha256"], sort_keys=True),
                                          meta["embedding_model"])
            except (ValueError, FileNotFoundError, PermissionError, KeyError) as exc:
                st.warning(f"Índice de políticas no disponible: {type(exc).__name__}")
    if indice is None and llm is not None:
        try:
            indice = indice_politicas_demo(huella_corpus())
        except Exception as exc:
            st.warning(f"Políticas ficticias no disponibles: {type(exc).__name__}")
    return llm, clasificador, indice


# --- Estado inicial y barra lateral --------------------------------------------------------

if "escenario" not in st.session_state:
    nuevo_escenario()
if "error_escenario" not in st.session_state:
    st.session_state.error_escenario = None
if "pasos" not in st.session_state:
    st.session_state.pasos = {}  # (sesión, número de mensaje) -> pasos del agente

with st.sidebar:
    st.title(":material/shopping_cart: Pedro")
    st.caption("Asistente de compras · datos ficticios")
    vista = st.segmented_control("Vista", ["Chat", "Comparación local"],
                                default="Chat", key="vista", width="stretch")
    with st.container(horizontal=True):
        st.button("Nuevo chat", on_click=nuevo_chat, icon=":material/edit_square:", width="stretch")
        st.button("Nuevo escenario", on_click=nuevo_escenario, icon=":material/refresh:",
                  width="stretch", help="Crea otra copia del catálogo y un chat nuevo")
    st.subheader("Conversaciones")
    for sesion in sesiones(MEMORIA, USUARIO)[:CONVERSACIONES_VISIBLES]:
        try:
            primero = next((m for m in Historial(MEMORIA, USUARIO, sesion["id"]).todos()
                            if m.type == "human"), None)
        except ValueError:
            primero = None
        titulo = str(primero.content)[:34] if primero else "Conversación nueva"
        actual = sesion["id"] == st.session_state.sesion
        st.button(titulo, key=f"sesion_{sesion['id']}", on_click=reabrir,
                  args=(sesion["id"], sesion["dataset_id"]), width="stretch",
                  type="primary" if actual else "secondary",
                  icon=":material/chat:" if actual else ":material/chat_bubble_outline:",
                  help=f"Sesión {sesion['id'][:8]} · escenario {sesion['dataset_id'][:8]}")

escenario = st.session_state.escenario
if escenario is None:
    st.warning(st.session_state.error_escenario or "Escenario ausente")
    st.stop()
con_agente = bool(os.getenv("OPENAI_API_KEY"))

if vista == "Chat":
    st.title("Chat")
    with st.container(horizontal=True):
        st.badge(f"Escenario {escenario.dataset_id[:8]}", icon=":material/database:", color="gray")
        if con_agente:
            st.badge("Agente activo", icon=":material/smart_toy:", color="green")
        else:
            st.badge("Modo local, sin modelo", icon=":material/offline_bolt:", color="orange")
        st.badge("Datos comerciales ficticios", icon=":material/science:", color="gray")
    mensajes = Historial(MEMORIA, USUARIO, st.session_state.sesion).todos()
    # El campo de entrada se fija abajo aunque se declare aquí; así se sabe ya si hay pregunta.
    pregunta = st.chat_input("Pregunta por piezas, ofertas, proveedores o políticas", key="pregunta",
                             submit_mode="disable") or st.session_state.pop("sugerida", None)
    for numero, mensaje in enumerate(mensajes):
        with st.chat_message("user" if mensaje.type == "human" else "assistant"):
            if mensaje.type == "human":
                st.markdown(str(mensaje.content))
                continue
            pasos = st.session_state.pasos.get((st.session_state.sesion, numero))
            if pasos:
                with st.expander(f"Cómo llegué a esta respuesta · {len(pasos)} pasos", type="compact"):
                    for paso in pasos:
                        mostrar_paso(paso)
            mostrar_mensaje(mensaje)
    if not mensajes and not pregunta:
        st.caption("Prueba con una de estas preguntas o escribe la tuya.")
        sugerencias = ["Compara 5 unidades de PEC-01-0001 con plazo de 7 días",
                       "Compara 5 unidades de PEC-02-0189", "Lista piezas"]
        if con_agente:
            sugerencias += ["¿Se puede mandar en varias cajas?",
                            "¿A qué ciudad corresponde el CEP 01001000?",
                            "¿Cuáles son las 5 piezas de mayor potencia?"]
        with st.container(horizontal=True):
            for texto in sugerencias:
                st.button(texto, key=f"sugerencia_{texto}", on_click=sugerir, args=(texto,))
        if not con_agente:
            st.info("Sin clave de OpenAI puedes listar piezas, comparar ofertas y ejecutar /t24. "
                    "Las políticas, el CEP y las preguntas abiertas necesitan el agente.",
                    title="Modo local", icon=":material/info:")
    if pregunta:
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            traza = Traza()
            traza.eventos = PasosEnVivo()
            salida = None
            with st.status(":shimmer[Consultando y verificando]", type="compact") as estado:
                llm, clasificador, indice = preparar_agente(es_diagnostico_t24(pregunta))
                flujo = crear_flujo(escenario, MEMORIA, llm=llm, clasificador=clasificador,
                                    indice=indice, traza=traza)
                try:
                    salida = flujo.invoke({"input": pregunta}, config={"configurable": {
                        "user_id": USUARIO, "session_id": st.session_state.sesion}})
                except Exception as exc:
                    estado.update(label=f"Consulta no completada: {type(exc).__name__}", state="error")
                else:
                    pasos = traza.eventos.pasos
                    estado.update(state="complete", label=(
                        f"Cómo llegué a esta respuesta · {len(pasos)} pasos" if pasos
                        else "Respondí con las reglas del catálogo, sin llamar al modelo"))
                    if pasos:
                        st.session_state.pasos[(st.session_state.sesion, len(mensajes) + 1)] = pasos
            if salida is not None:
                mostrar_mensaje(salida)

else:
    st.title("Comparación local")
    st.caption("Cálculo determinista en centavos sobre las ofertas del escenario activo. No usa el modelo.")
    with st.form("comparacion", border=True):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            producto_id = st.text_input("ID de pieza", placeholder="PEC-01-0001")
            cantidad = st.number_input("Cantidad", min_value=1, value=5, step=1)
            presupuesto = st.text_input("Presupuesto máximo (R$), opcional", placeholder="Sin límite")
            plazo = st.text_input("Plazo máximo (días), opcional", placeholder="Sin límite")
        enviado = st.form_submit_button("Comparar proveedores", icon=":material/compare_arrows:",
                                        type="primary")
    if enviado:
        try:
            cifra = presupuesto.strip()
            if "," in cifra:
                cifra = cifra.replace(".", "").replace(",", ".")
            elif "." in cifra and len(cifra.rsplit(".", 1)[1]) == 3:
                cifra = cifra.replace(".", "")
            importe = Decimal(cifra) if cifra else None
            if importe is not None and (not importe.is_finite() or importe < 0 or
                                       int(importe.as_tuple().exponent) < -2):
                raise ValueError("Presupuesto inválido; indique hasta dos decimales.")
            solicitud = Solicitud(producto_id=producto_id.upper().strip(), cantidad=int(cantidad),
                                 presupuesto_centavos=int(importe * 100) if importe is not None else None,
                                 plazo_max_dias=int(plazo) if plazo.strip() else None)
            if solicitud.producto_id is None or ficha(escenario, solicitud.producto_id) is None:
                st.warning("No encontré ese ID de pieza en este escenario.", icon=":material/search_off:")
            else:
                respuesta = respuesta_local(escenario, solicitud)
                errores = verificar(respuesta, escenario)
                if errores:
                    st.error(", ".join(errores), title="La comparación no superó la verificación")
                else:
                    mostrar_comparacion(respuesta)
        except (ValueError, InvalidOperation) as exc:
            st.error(str(exc), icon=":material/error:")
