"""Interfaz local: chat, catálogo y comparación de piezas ficticias."""
import os
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pedro.agent import crear_flujo, es_diagnostico_t24
from pedro.business import brl, describir_motivos
from pedro.catalog import abrir_escenario, crear_escenario, ficha, listar, ofertas
from pedro.contracts import Solicitud
from pedro.memory import MODELO_RECUERDOS, Historial, nueva_sesion, sesiones
from pedro.policy_demo import crear_indice_demo, huella_corpus
from pedro.verification import respuesta_local, verificar

load_dotenv()
BASE = Path(os.getenv("PEDRO_STORAGE", "storage"))
CATALOGOS = BASE / "catalogos"
MEMORIA = BASE / "memoria.sqlite3"
USUARIO = "usuario-demo"
st.set_page_config(page_title="Pedro · compras ficticias", page_icon=":material/shopping_cart:",
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


if "escenario" not in st.session_state:
    nuevo_escenario()
if "error_escenario" not in st.session_state:
    st.session_state.error_escenario = None

with st.sidebar:
    st.title("Pedro")
    st.caption("Compras ficticias · usuario-demo")
    vista = st.segmented_control("Vista", ["Chat", "Catálogo de piezas", "Comparación local"],
                                default="Chat", key="vista", width="stretch")
    st.button("Nuevo chat", on_click=nuevo_chat, icon=":material/edit_square:", width="stretch")
    st.button("Nuevo escenario", on_click=nuevo_escenario, icon=":material/refresh:", width="stretch")
    st.subheader("Conversaciones")
    for sesion in sesiones(MEMORIA, USUARIO):
        st.button(f"{sesion['id'][:8]} · {sesion['dataset_id'][:8]}", key=f"sesion_{sesion['id']}",
                  on_click=reabrir, args=(sesion["id"], sesion["dataset_id"]), width="stretch")

escenario = st.session_state.escenario
if escenario is None:
    st.warning(st.session_state.error_escenario or "Escenario ausente")
    st.stop()

if vista == "Chat":
    st.title("Chat")
    st.caption(f"Escenario {escenario.dataset_id[:8]} · datos comerciales ficticios")
    st.caption("Las políticas ficticias de demostración se usan cuando no hay un índice autorizado disponible.")
    st.caption("Pregunta «¿Se puede mandar en varias cajas?» para probar T24 en el flujo normal; /t24 muestra el diagnóstico controlado.")
    for mensaje in Historial(MEMORIA, USUARIO, st.session_state.sesion).todos():
        with st.chat_message("user" if mensaje.type == "human" else "assistant"):
            st.markdown(str(mensaje.content))
    if not os.getenv("OPENAI_API_KEY"):
        st.info("Puedes listar piezas, comparar ofertas y ejecutar /t24 sin clave. Para otras preguntas sobre políticas o CEP se requiere el agente OpenAI.")
    pregunta = st.chat_input("Pregunta por piezas, ofertas o políticas", key="pregunta")
    if pregunta:
        prueba_t24 = es_diagnostico_t24(pregunta)
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            with st.status("Consultando y verificando", expanded=False):
                llm = None
                clasificador = None
                if os.getenv("OPENAI_API_KEY") and not prueba_t24:
                    from langchain_openai import ChatOpenAI
                    llm = ChatOpenAI(model=os.getenv("PEDRO_MODEL", "gpt-4.1-mini"))
                    try:
                        clasificador = modelo_nli()
                    except Exception:
                        st.warning("NLI no disponible; las recomendaciones quedarán bloqueadas.")
                indice = None
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
                            indice = indice_politicas(str(carpeta),
                                                       json.dumps(meta["sha256"], sort_keys=True),
                                                       meta["embedding_model"])
                        except (ValueError, FileNotFoundError, PermissionError, KeyError) as exc:
                            st.warning(f"Índice de políticas no disponible: {type(exc).__name__}")
                if indice is None and llm is not None:
                    try:
                        indice = indice_politicas_demo(huella_corpus())
                    except Exception as exc:
                        st.warning(f"Políticas ficticias no disponibles: {type(exc).__name__}")
                flujo = crear_flujo(escenario, MEMORIA, llm=llm,
                                   clasificador=clasificador, indice=indice)
                try:
                    salida = flujo.invoke({"input": pregunta}, config={"configurable": {
                        "user_id": USUARIO, "session_id": st.session_state.sesion}})
                    st.markdown(str(salida.content))
                except Exception as exc:
                    st.error(f"Consulta no completada: {type(exc).__name__}")

elif vista == "Catálogo de piezas":
    st.title("Catálogo de piezas")
    st.caption("Fuente: copia SQLite sintética del escenario activo. Ofertas y compatibilidades ficticias.")
    termino = st.text_input("Buscar por nombre, SKU o ID", key="termino")
    pagina = st.number_input("Página", min_value=1, value=1, step=1, key="pagina")
    total, piezas = listar(escenario, int(pagina), termino)
    st.caption(f"{total} piezas · hasta 20 por página")
    st.dataframe(piezas, hide_index=True, width="stretch", alt="Piezas del escenario activo")
    ids = [p["id"] for p in piezas]
    producto_id = st.selectbox("Ficha técnica", ids, index=None, key="ficha_id")
    if producto_id:
        dato = ficha(escenario, producto_id)
        if dato is None:
            st.warning("La pieza ya no está disponible.")
            st.stop()
        st.subheader(dato["name"])
        st.markdown(dato["description"])
        st.dataframe([{"SKU": dato["sku"], "Material": dato["material"],
                       "Voltaje V": dato["voltage_v"], "Garantía meses": dato["warranty_months"]}],
                     hide_index=True, alt="Ficha técnica de la pieza")
        st.dataframe(dato["compatibility"], hide_index=True, alt="Compatibilidades ficticias")
        st.dataframe([o.model_dump(exclude={"dataset_id"}) for o in ofertas(escenario, producto_id)],
                     hide_index=True, alt="Ofertas vigentes del escenario")

else:
    st.title("Comparación local")
    st.caption("Cálculo determinista en centavos sobre ofertas ficticias del escenario activo.")
    with st.form("comparacion"):
        producto_id = st.text_input("ID de pieza", placeholder="PEC-01-0001")
        cantidad = st.number_input("Cantidad", min_value=1, value=2, step=1)
        presupuesto = st.text_input("Presupuesto máximo opcional (R$)", placeholder="Sin límite")
        plazo = st.text_input("Plazo máximo opcional (días corridos)", placeholder="Sin límite")
        enviado = st.form_submit_button("Comparar", width="stretch")
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
                st.warning("ID de pieza no encontrado.")
            else:
                respuesta = respuesta_local(escenario, solicitud)
                errores = verificar(respuesta, escenario)
                if errores:
                    st.error("La comparación no superó la verificación: " + ", ".join(errores))
                elif respuesta.estado == "sin_oferta":
                    st.warning("Ninguna oferta cumple todas las restricciones.")
                elif respuesta.total_centavos is not None:
                    st.success(f"{respuesta.proveedor_id}: {brl(respuesta.total_centavos)}")
                if not errores:
                    st.dataframe([{"Proveedor": a.oferta.proveedor_nombre,
                                   "Total": brl(a.total_centavos), "Cumple": a.cumple,
                                   "Origen": "nacional" if a.oferta.nacional else "internacional",
                                   "Pedido mínimo": a.oferta.pedido_minimo,
                                   "Descartes": describir_motivos(a), "Fuente": a.oferta.id}
                                  for a in respuesta.alternativas], hide_index=True,
                                 alt="Todas las ofertas, totales y descartes")
        except (ValueError, InvalidOperation) as exc:
            st.error(str(exc))
