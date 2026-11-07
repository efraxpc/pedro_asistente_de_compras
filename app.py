"""Interfaz local y chat online. La respuesta online solo aparece tras verificar."""
import os
from pathlib import Path
from decimal import Decimal

import streamlit as st
from dotenv import load_dotenv

from compraslab.business import comparar_ofertas, formatar_brl
from compraslab.data import buscar_productos, crear_catalogo, ofertas_producto
from compraslab.memory import nueva_sesion
from compraslab.schemas import Evidencia, RespuestaCompra, SolicitudCompra
from compraslab.verification import verificar
from compraslab.memory import HistorialSQLite

BASE = Path("storage")
load_dotenv()
st.set_page_config(page_title="Pedro — Asistente de Compras", page_icon="🛒")
st.title("Pedro — Asistente de Compras")
st.caption("Datos ficticios. Las políticas originales siguen pendientes.")

if "catalogo" not in st.session_state:
    st.session_state.catalogo = crear_catalogo(BASE / "catalogos")
if "session_id" not in st.session_state:
    st.session_state.session_id = nueva_sesion(BASE / "memoria.sqlite3", "usuario-demo",
                                              st.session_state.catalogo.dataset_id)

col1, col2 = st.columns(2)
if col1.button("Nuevo chat"):
    st.session_state.session_id = nueva_sesion(BASE / "memoria.sqlite3", "usuario-demo",
                                              st.session_state.catalogo.dataset_id)
    st.rerun()
if col2.button("Nuevo escenario"):
    st.session_state.catalogo = crear_catalogo(BASE / "catalogos")
    st.session_state.session_id = nueva_sesion(BASE / "memoria.sqlite3", "usuario-demo",
                                              st.session_state.catalogo.dataset_id)
    st.rerun()

modo = st.radio("Modo", ["Comparación local", "Chat con agente"], horizontal=True)
if modo == "Chat con agente":
    if not os.getenv("OPENAI_API_KEY"):
        st.info("Configure OPENAI_API_KEY para el chat con modelo real.")
    else:
        from langchain_openai import ChatOpenAI
        from compraslab.agent import crear_agente, crear_integrador
        from compraslab.nli import NLIConModelo, verificar_nli

        modelo = os.getenv("COMPRASLAB_MODEL", "gpt-4.1-mini")
        historial_actual = HistorialSQLite(BASE / "memoria.sqlite3",
                                          st.session_state.session_id, "usuario-demo")
        for mensaje in historial_actual.messages:
            with st.chat_message("user" if mensaje.type == "human" else "assistant"):
                st.write(mensaje.content)
        pregunta = st.chat_input("Describe tu solicitud de compra")
        if pregunta:
            with st.chat_message("user"):
                st.write(pregunta)
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
            with st.chat_message("assistant"):
                st.write(texto_salida)

if modo == "Comparación local":
    st.subheader("Comparar ofertas del catálogo activo")
    with st.form("solicitud"):

        texto = st.text_input("Producto o modelo")
        cantidad = st.number_input("Cantidad", min_value=1, value=20, step=1)
        presupuesto = st.number_input("Presupuesto máximo (R$)", min_value=0.0, value=12000.0, step=100.0)
        plazo = st.number_input("Plazo máximo (días corridos)", min_value=0, value=7, step=1)
        enviar = st.form_submit_button("Comparar")

    if enviar:
        candidatos = buscar_productos(st.session_state.catalogo, texto) if texto.strip() else []
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
