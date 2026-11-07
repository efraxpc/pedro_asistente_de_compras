"""Interfaz local y chat online. La respuesta online solo aparece tras verificar."""
import os
from pathlib import Path
from decimal import Decimal

import httpx
import streamlit as st
from dotenv import load_dotenv

from compraslab.business import comparar_ofertas, formatar_brl
from compraslab.data import (abrir_catalogo, buscar_productos, crear_catalogo,
                             listar_productos, ofertas_producto)
from compraslab.memory import listar_sesiones, mensajes_sesion, nueva_sesion
from compraslab.schemas import Evidencia, RespuestaCompra, SolicitudCompra
from compraslab.verification import verificar
from compraslab.memory import HistorialSQLite

BASE = Path("storage")
load_dotenv()
st.set_page_config(page_title="Pedro — Asistente de Compras", page_icon=":material/chat:",
                   layout="wide", initial_sidebar_state="expanded")


def crear_catalogo_app():
    modo = os.getenv("COMPRASLAB_CATALOG_SOURCE", "dummyjson").lower()
    try:
        return crear_catalogo(BASE / "catalogos", modo=modo)
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"No se pudo cargar el catálogo de {modo}: {type(exc).__name__}. Intente de nuevo.")
        st.stop()


if "catalogo" not in st.session_state:
    st.session_state.catalogo = crear_catalogo_app()
if "session_id" not in st.session_state:
    st.session_state.session_id = nueva_sesion(BASE / "memoria.sqlite3", "usuario-demo",
                                              st.session_state.catalogo.dataset_id)


def iniciar_chat() -> None:
    if st.session_state.catalogo is None:
        st.session_state.catalogo = crear_catalogo_app()
    st.session_state.session_id = nueva_sesion(BASE / "memoria.sqlite3", "usuario-demo",
                                              st.session_state.catalogo.dataset_id)
    st.session_state.vista = "Chat"


def nuevo_escenario() -> None:
    st.session_state.catalogo = crear_catalogo_app()
    iniciar_chat()


def abrir_sesion(session_id: str, dataset_id: str) -> None:
    st.session_state.session_id = session_id
    try:
        st.session_state.catalogo = abrir_catalogo(BASE / "catalogos" / dataset_id)
    except (FileNotFoundError, ValueError):
        st.session_state.catalogo = None
    st.session_state.vista = "Chat"


with st.sidebar:
    st.title("Pedro")
    st.caption("Asistente de compras")
    if st.session_state.catalogo is not None:
        fuente = "DummyJSON" if st.session_state.catalogo.modo == "dummyjson" else "catálogo local"
        st.caption(f"Productos: {fuente} · ofertas simuladas")
    vista = st.segmented_control("Vista", ["Chat", "Comparación local"],
                                key="vista", default="Chat", width="stretch")
    st.button("Nuevo chat", icon=":material/edit_square:", width="stretch",
              on_click=iniciar_chat)
    st.button("Nuevo escenario", icon=":material/refresh:", width="stretch",
              on_click=nuevo_escenario)
    st.subheader("Conversaciones")
    st.html("""<style>
        .st-key-chat_list button {
            border: 0;
            box-shadow: none;
            justify-content: flex-start;
            text-align: left;
            min-height: 2.25rem;
        }
        .st-key-chat_list button p { width: 100%; text-align: left; }
        .st-key-chat_list button[kind="secondary"] { background: transparent; }
        .st-key-chat_list button[kind="primary"] {
            background: #E8E8F7;
            color: #3F427F;
        }
    </style>""")
    with st.container(key="chat_list"):
        for sesion in listar_sesiones(BASE / "memoria.sqlite3", "usuario-demo"):
            activa = sesion["session_id"] == st.session_state.session_id
            st.button(sesion["titulo"], key=f"chat_{sesion['session_id']}",
                      type="primary" if activa else "secondary", width="stretch",
                      on_click=abrir_sesion, args=(sesion["session_id"], sesion["dataset_id"]))

if vista == "Chat":
    st.subheader("Pedro")
    st.caption("Asistente de compras · Datos ficticios")
    catalogo_disponible = st.session_state.catalogo is not None
    if not catalogo_disponible:
        st.warning("El catálogo de esta conversación ya no está disponible. Puede consultar el historial.")
    for mensaje in mensajes_sesion(BASE / "memoria.sqlite3", st.session_state.session_id,
                                   "usuario-demo"):
        with st.chat_message("user" if mensaje.type == "human" else "assistant",
                             avatar=":material/person:" if mensaje.type == "human" else ":material/smart_toy:"):
            st.write(mensaje.content)
    if not os.getenv("OPENAI_API_KEY"):
        st.info("Configure OPENAI_API_KEY para conversar con Pedro.")
    pregunta = st.chat_input("Escribe un mensaje a Pedro", key="mensaje_chat",
                             disabled=not os.getenv("OPENAI_API_KEY") or not catalogo_disponible)
    if pregunta:
        from langchain_openai import ChatOpenAI
        from compraslab.agent import crear_agente, crear_integrador
        from compraslab.nli import NLIConModelo, verificar_nli

        modelo = os.getenv("COMPRASLAB_MODEL", "gpt-4.1-mini")
        with st.chat_message("user", avatar=":material/person:"):
            st.write(pregunta)
        with st.chat_message("assistant", avatar=":material/smart_toy:"):
            with st.status("Consultando y verificando", expanded=False):
                llm = ChatOpenAI(model=modelo)
                indice = None
                carpeta_indice = Path("knowledge/politicas")
                if (carpeta_indice / "manifest.json").is_file():
                    if os.getenv("COMPRASLAB_TRUST_POLICY_INDEX", "false").lower() != "true":
                        st.warning("El índice de políticas existe, pero su origen debe verificarse antes de cargar el docstore.")
                    else:
                        try:
                            import json
                            from langchain_openai import OpenAIEmbeddings
                            from compraslab.rag import cargar_indice_politicas
                            meta = json.loads((carpeta_indice / "manifest.json").read_text(encoding="utf-8"))
                            modelo_embeddings = meta.get("embedding_model", "")
                            if not modelo_embeddings.startswith("text-embedding-"):
                                raise ValueError("modelo de embeddings no admitido")
                            indice, _ = cargar_indice_politicas(carpeta_indice,
                                OpenAIEmbeddings(model=modelo_embeddings), origen_confiable=True)
                        except (ValueError, FileNotFoundError) as exc:
                            st.warning(f"Índice de políticas no disponible: {exc}")
                executor = crear_agente(st.session_state.catalogo, model=modelo,
                    simulado=os.getenv("COMPRASLAB_INTEGRATION_MODE") == "simulated", llm=llm,
                    memoria_db=BASE / "memoria.sqlite3", user_id="usuario-demo", mensaje_actual=pregunta,
                    indice=indice)
                clasificador = NLIConModelo(llm)
                integrador = crear_integrador(executor, st.session_state.catalogo,
                    BASE / "memoria.sqlite3", nli=lambda r: verificar_nli(r, clasificador))
                try:
                    salida = integrador.invoke({"input": pregunta}, config={"configurable": {
                        "user_id": "usuario-demo", "session_id": st.session_state.session_id}})
                    texto_salida = salida.content
                except Exception as exc:
                    texto_salida = f"No se pudo completar la consulta: {type(exc).__name__}."
            st.write(texto_salida)

if vista == "Comparación local":
    st.title("Comparación local")
    st.caption("Datos ficticios. Las políticas originales siguen pendientes.")
    if st.session_state.catalogo is None:
        st.warning("El catálogo de esta conversación ya no está disponible. Cree un escenario nuevo.")
        st.stop()
    st.subheader("Comparar ofertas del catálogo activo")
    with st.form("solicitud"):
        producto_seleccionado = None
        texto = ""
        if st.session_state.catalogo.modo == "dummyjson":
            producto_seleccionado = st.selectbox(
                "Producto o modelo", listar_productos(st.session_state.catalogo), index=None,
                placeholder="Busca o selecciona un producto",
                format_func=lambda p: f"{p.nombre} · {p.modelo}")
        else:
            texto = st.text_input("Producto o modelo")
        cantidad = st.number_input("Cantidad", min_value=1, value=20, step=1)
        presupuesto = st.number_input("Presupuesto máximo (R$)", min_value=0.0, value=12000.0, step=100.0)
        plazo = st.number_input("Plazo máximo (días corridos)", min_value=0, value=7, step=1)
        enviar = st.form_submit_button("Comparar")

    if enviar:
        candidatos = ([producto_seleccionado] if producto_seleccionado else
                      buscar_productos(st.session_state.catalogo, texto) if texto.strip() else [])
        if not candidatos:
            st.info("Indique un producto presente en el catálogo.")
        elif len(candidatos) > 1:
            st.info("Hay varios productos posibles. Especifique el ID o modelo: " +
                    ", ".join(f"{p.id} ({p.modelo})" for p in candidatos))
        else:
            producto = candidatos[0]
            solicitud = SolicitudCompra(producto_id=producto.id, cantidad=int(cantidad),
            presupuesto_centavos=int(Decimal(str(presupuesto)) * 100), plazo_max_dias=int(plazo))
            alternativas = comparar_ofertas(solicitud, ofertas_producto(st.session_state.catalogo, producto.id))
            validas = [a for a in alternativas if a.cumple]
            if not validas:
                st.warning("Ninguna oferta cumple todas las restricciones.")
            else:
                ganadora = validas[0]
                respuesta = RespuestaCompra(estado="recomendacion", mensaje="Oferta calculada", dataset_id=producto.dataset_id,
                    solicitud=solicitud, producto_id=producto.id, proveedor_id=ganadora.oferta.proveedor_id,
                    total_centavos=ganadora.total_centavos, alternativas=alternativas,
                    evidencias=[Evidencia(tipo="catalogo", fuente_id=a.oferta.id,
                                          dataset_id=producto.dataset_id, texto=a.oferta.proveedor_nombre)
                                for a in alternativas])
                verificacion = verificar(respuesta, st.session_state.catalogo)
                if verificacion.aprobado:
                    st.success(f"{ganadora.oferta.proveedor_nombre}: {formatar_brl(ganadora.total_centavos)}")
                else:
                    st.error("La recomendación no superó la verificación.")
            for a in alternativas:
                st.write(a.oferta.proveedor_nombre, formatar_brl(a.total_centavos),
                         "cumple" if a.cumple else "descartada: " + ", ".join(a.motivos))
