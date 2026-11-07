"""Interfaz local y chat online. La respuesta online solo aparece tras verificar."""
import os
import sqlite3
from pathlib import Path
from decimal import Decimal

import streamlit as st
from dotenv import load_dotenv

from compraslab.business import comparar_ofertas, formatar_brl
from compraslab.data import (Catalogo, abrir_catalogo, crear_catalogo,
                             listar_productos, ofertas_producto, PIEZAS_DB)
from compraslab.part_catalog import detalle_pieza, listar_piezas
from compraslab.memory import listar_sesiones, mensajes_sesion, nueva_sesion
from compraslab.schemas import Evidencia, RespuestaCompra, SolicitudCompra
from compraslab.verification import verificar
from compraslab.memory import HistorialSQLite

BASE = Path("storage")
load_dotenv()
st.set_page_config(page_title="Pedro — Asistente de Compras", page_icon=":material/chat:",
                   layout="wide", initial_sidebar_state="expanded")


def crear_catalogo_app():
    try:
        return crear_catalogo(BASE / "catalogos")
    except (ValueError, FileNotFoundError, sqlite3.DatabaseError) as exc:
        st.error(f"No se pudo cargar la base SQLite de piezas: {type(exc).__name__}. Intente de nuevo.")
        st.stop()


@st.cache_data(show_spinner=False, max_entries=8)
def piezas_para_vista(catalogo: Catalogo, version_db: int) -> list[dict]:
    return listar_piezas(catalogo)


if "catalogo" not in st.session_state:
    st.session_state.catalogo = crear_catalogo_app()
elif (st.session_state.catalogo is not None and
      st.session_state.catalogo.modo != "piezas"):
    st.session_state.catalogo = crear_catalogo_app()
    st.session_state.session_id = nueva_sesion(BASE / "memoria.sqlite3", "usuario-demo",
                                              st.session_state.catalogo.dataset_id)
    st.session_state.vista = "Chat"
if "session_id" not in st.session_state:
    st.session_state.session_id = nueva_sesion(BASE / "memoria.sqlite3", "usuario-demo",
                                              st.session_state.catalogo.dataset_id)
if "vista" not in st.session_state:
    st.session_state.vista = "Chat"


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
        st.caption("Productos: base SQLite de piezas · ofertas simuladas")
    vista = st.segmented_control("Vista", ["Chat", "Catálogo de piezas", "Comparación local"],
                                key="vista", width="stretch")
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
        st.info("Puede consultar piezas, detalles y su fuente. Configure OPENAI_API_KEY para recomendaciones.")
    pregunta = st.chat_input("Escribe un mensaje a Pedro", key="mensaje_chat",
                             disabled=not catalogo_disponible)
    if pregunta:
        from compraslab.agent import crear_integrador, responder_consulta_catalogo
        from langchain_openai import ChatOpenAI

        modelo = os.getenv("COMPRASLAB_MODEL", "gpt-4.1-mini")
        with st.chat_message("user", avatar=":material/person:"):
            st.write(pregunta)
        if (responder_consulta_catalogo(st.session_state.catalogo, pregunta) is not None
                or not os.getenv("OPENAI_API_KEY")):
            integrador = crear_integrador(None, st.session_state.catalogo,
                                         BASE / "memoria.sqlite3")
            salida = integrador.invoke({"input": pregunta}, config={"configurable": {
                "user_id": "usuario-demo", "session_id": st.session_state.session_id}})
            with st.chat_message("assistant", avatar=":material/smart_toy:"):
                st.write(salida.content)
            st.rerun()
        from compraslab.agent import crear_agente
        from compraslab.nli import NLIConModelo, verificar_nli

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

if vista == "Catálogo de piezas":
    catalogo = st.session_state.catalogo
    st.title("Catálogo de piezas")
    st.caption("Datos ficticios de la base SQLite local · precios en BRL estimados")
    if catalogo is None:
        st.warning("El catálogo de esta conversación ya no está disponible. Cree un escenario nuevo.")
        st.stop()
    piezas = piezas_para_vista(catalogo, PIEZAS_DB.stat().st_mtime_ns)
    categorias = sorted({pieza["category"] for pieza in piezas})
    categoria = st.selectbox("Categoría", ["Todas", *categorias], key="categoria_piezas")
    busqueda = st.text_input("Buscar por nombre, SKU, ID o tipo", key="buscar_piezas")
    termino = busqueda.strip().casefold()
    filtradas = [pieza for pieza in piezas
                 if (categoria == "Todas" or pieza["category"] == categoria)
                 and (not termino or any(termino in str(pieza[campo]).casefold()
                                        for campo in ("name", "sku", "product_id", "part_kind")))]
    st.caption(f"{len(filtradas)} de {len(piezas)} piezas del escenario activo")
    st.dataframe([{
        "ID": p["product_id"], "SKU": p["sku"], "Pieza": p["name"],
        "Categoría": p["category"], "Tipo": p["part_kind"],
        "Fabricante": p["manufacturer"],
        "Desde (R$)": p["min_price_brl_cents"] / 100 if p["min_price_brl_cents"] is not None else None,
        "Stock total": p["total_stock"], "Ofertas": p["offer_count"]
    } for p in filtradas], hide_index=True, width="stretch",
        alt="Todas las piezas del escenario activo con precio mínimo, stock y ofertas")
    etiquetas = {p["sku"]: f"{p['name']} · {p['sku']}" for p in filtradas}
    sku = st.selectbox("Ver detalles de una pieza", list(etiquetas),
                       index=None, placeholder="Seleccione un SKU", key="detalle_sku",
                       format_func=lambda value: etiquetas[value])
    if sku:
        detalle = detalle_pieza(catalogo, sku)
        if detalle is None:
            st.warning("La pieza ya no está disponible en este escenario.")
        else:
            st.subheader(f"{detalle['name']} · {detalle['product_id']}")
            st.write(detalle["description"])
            st.dataframe([{
                "SKU": detalle["sku"], "Categoría": detalle["category"],
                "Familia": detalle["family"], "Fabricante": detalle["manufacturer"],
                "Tipo": detalle["part_kind"], "Material": detalle["material"],
                "Color": detalle["color"], "Voltaje (V)": detalle["voltage_v"],
                "Potencia (W)": detalle["power_w"],
                "Dimensiones (mm)": f"{detalle['length_mm']} × {detalle['width_mm']} × {detalle['height_mm']}",
                "Peso (g)": detalle["weight_g"], "Garantía (meses)": detalle["warranty_months"],
                "Origen": detalle["origin_country"], "Estado": detalle["condition"]
            }], hide_index=True, width="stretch", alt="Especificaciones de la pieza seleccionada")
            st.write("Especificaciones adicionales", detalle["technical_specs"])
            st.subheader("Compatibilidad ficticia")
            st.dataframe([{"Marca": c["brand"], "Modelo": c["model_code"],
                           "Desde año": c["year_from"], "Hasta año": c["year_to"]}
                          for c in detalle["compatibility"]], hide_index=True, width="stretch",
                         alt="Modelos y años compatibles con la pieza seleccionada")
            st.subheader("Ofertas ficticias")
            st.dataframe([{
                "Proveedor": o["supplier_name"], "País": o["country_code"],
                "Ámbito": "Nacional" if o["domestic"] else "Internacional",
                "Precio origen": f"{o['unit_price_minor'] / 100:.2f} {o['currency']}",
                "Estimado BRL": formatar_brl(o["estimated_brl_cents"]),
                "Stock": o["stock_qty"], "Disponibilidad": o["availability"],
                "Reposición": o["restock_date"],
                "Flete": formatar_brl(o["shipping_brl_cents"]),
                "Plazo (días)": o["lead_days"], "Pedido mínimo": o["min_order_qty"],
                "Actualizado": o["updated_on"], "Sitio": o["website"]
            } for o in detalle["offers"]], hide_index=True, width="stretch",
                alt="Precios, disponibilidad y proveedores de la pieza seleccionada")
            st.subheader("Historial de precios")
            proveedores_por_oferta = {o["id"]: o for o in detalle["offers"]}
            st.dataframe([{
                "Proveedor": proveedores_por_oferta[offer_id]["supplier_name"],
                "Fecha": h["observed_on"],
                "Precio origen": f"{h['unit_price_minor'] / 100:.2f} {proveedores_por_oferta[offer_id]['currency']}",
                "Estimado BRL": formatar_brl(h["estimated_brl_cents"])
            } for offer_id, history in detalle["price_history"].items() for h in history],
                hide_index=True, width="stretch", alt="Historial de precios de todas las ofertas")

if vista == "Comparación local":
    st.title("Comparación local")
    st.caption("Datos ficticios. Las políticas originales siguen pendientes.")
    if st.session_state.catalogo is None:
        st.warning("El catálogo de esta conversación ya no está disponible. Cree un escenario nuevo.")
        st.stop()
    st.subheader("Comparar ofertas del catálogo activo")
    with st.form("solicitud"):
        producto_seleccionado = st.selectbox(
            "Producto o modelo", listar_productos(st.session_state.catalogo), index=None,
            placeholder="Busca o selecciona un producto",
            format_func=lambda p: f"{p.nombre} · {p.modelo}")
        cantidad = st.number_input("Cantidad", min_value=1, value=20, step=1)
        presupuesto = st.number_input("Presupuesto máximo (R$)", min_value=0.0, value=12000.0, step=100.0)
        plazo = st.number_input("Plazo máximo (días corridos)", min_value=0, value=7, step=1)
        enviar = st.form_submit_button("Comparar")

    if enviar:
        candidatos = [producto_seleccionado] if producto_seleccionado else []
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
