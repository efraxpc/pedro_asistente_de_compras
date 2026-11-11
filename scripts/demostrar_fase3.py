"""Fase 3 con el modelo real: chatbot con memoria, intenciones y entidades, conversación compleja.

Requiere OPENAI_API_KEY. Llama a OpenAI y a ViaCEP; el catálogo y las políticas son sintéticos.
Cada bloque guarda lo observado; nada se simula.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Traza, crear_flujo
from pedro.catalog import crear_escenario
from pedro.chains import crear_variantes_de_prompt
from pedro.dialogue import interpretar_compra
from pedro.legacy import crear_chatbot_buffer
from pedro.memory import (FastEmbedder, Historial, leer_borrador, mapa_memorias, nueva_sesion,
                          preferencias, recuperar)
from pedro.nli import ModeloNLI
from pedro.rag import cargar_indice, inspeccionar_indice

ROOT = Path(__file__).resolve().parents[1]
CHATBOT = ["Hola, soy Ana. Necesito un termostato para mi nevera.",
           "Que sean 2 unidades.",
           "Tengo hasta R$ 900 y lo necesito en 5 días.",
           "Resume mi solicitud completa y dime cómo me llamo."]
MENSAJES = ["Compara 2 unidades de PEC-01-0001 hasta R$ 5.000 en 7 días",
            "Necesito un termostato para nevera",
            "¿A qué ciudad corresponde el CEP 01001000?",
            "¿Qué dice la política de devoluciones?",
            "Prefiero proveedores nacionales, recuérdalo",
            "Quiero media docena de PEC-02-0001 sin límite de gasto",
            "Hola, ¿qué puedes hacer?"]
COMPLEJA = ["Necesito 2 unidades de PEC-01-0001 con plazo máximo de 7 días",
            "Ahora que sean 3 y mantén el plazo",
            "Mejor sin límite de plazo, pero con presupuesto de R$ 5.000",
            "Prefiero proveedores nacionales, recuérdalo",
            "¿A qué ciudad corresponde el CEP 01001000?",
            "¿Cómo se comprueba la compatibilidad eléctrica antes de instalar una pieza?",
            "Vuelve a comparar con lo último que te pedí"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/fase3_memoria_llm.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    llm = ChatOpenAI(model=modelo, temperature=0)
    escenario = crear_escenario(ROOT / "storage/evidencias/fase3_catalogos")
    memoria = ROOT / f"storage/evidencias/fase3_memoria-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.sqlite3"

    # R16: chatbot con ConversationBufferMemory.
    chatbot, buffer = crear_chatbot_buffer(llm)
    r16 = []
    for texto in CHATBOT:
        respuesta = chatbot.invoke({"input": texto})["response"]
        r16.append({"usuario": texto, "pedro": respuesta,
                    "caracteres_en_memoria": len(buffer.load_memory_variables({})["history"])})
        print("R16 |", texto, "->", respuesta[:150].replace("\n", " "))

    # R17: intención y entidades con el modelo (few-shot) y con las reglas del chat.
    extractor = crear_variantes_de_prompt(llm)["few-shot"]
    r17 = []
    for texto, extraccion in zip(MENSAJES, extractor.batch([{"texto": t} for t in MENSAJES])):
        reglas = interpretar_compra(escenario, None, texto)
        r17.append({
            "mensaje": texto, "intencion_llm": extraccion.intencion,
            "entidades_llm": extraccion.solicitud.model_dump(exclude_none=True),
            "faltantes": extraccion.solicitud.faltantes(),
            "reglas_del_chat": None if reglas is None else {
                "entidades": reglas[0].solicitud.model_dump(exclude_none=True),
                "aclaracion": reglas[1]}})
        print("R17 |", texto, "->", extraccion.intencion,
              extraccion.solicitud.model_dump(exclude_none=True), "| reglas:",
              None if reglas is None else reglas[1])

    # R18 (y R13, R14, R15): conversación compleja con el agente final y su memoria.
    manifiesto = inspeccionar_indice(ROOT / "knowledge/politicas")
    indice, _ = cargar_indice(ROOT / "knowledge/politicas", FastEmbedEmbeddings(
        model_name=manifiesto["embedding_model"], doc_embed_type="passage"), origen_confiable=True)
    nli = ModeloNLI()
    usuario = "ana"
    sesion = nueva_sesion(memoria, usuario, escenario.dataset_id)
    traza = Traza()
    flujo = crear_flujo(escenario, memoria, llm=ChatOpenAI(model=modelo), clasificador=nli,
                        indice=indice, traza=traza)
    r18 = []
    for texto in COMPLEJA:
        desde = len(traza.eventos)
        respuesta = flujo.invoke({"input": texto}, config={"configurable": {
            "user_id": usuario, "session_id": sesion}}).content
        eventos = traza.eventos[desde:]
        borrador = leer_borrador(memoria, usuario, sesion)
        r18.append({
            "usuario": texto,
            "herramientas": [e["herramienta"] + " " + e["entrada"] for e in eventos
                             if e["evento"] == "tool_start"],
            "verificaciones": [e["errores"] for e in eventos if e["evento"] == "verificacion"],
            "borrador_tras_el_turno": {k: v for k, v in (borrador or {}).get("solicitud", {}).items()
                                       if v is not None},
            "respuesta_publicada": respuesta})
        print("R18 |", texto, "->", [h.split()[0] for h in r18[-1]["herramientas"]],
              r18[-1]["borrador_tras_el_turno"], "|", respuesta.splitlines()[0][:90])

    # Persistencia y aislamiento: se crea otro flujo (como tras reiniciar) sobre la misma base.
    mapa = mapa_memorias(memoria, usuario, sesion)
    reinicio = Historial(memoria, usuario, sesion)
    otra_sesion = nueva_sesion(memoria, usuario, escenario.dataset_id)
    otro_usuario_sesion = nueva_sesion(memoria, "luis", escenario.dataset_id)
    pregunta_recuerdo = "¿Qué proveedor me convenía para el compresor PEC-01-0001?"
    embedder = FastEmbedder()
    persistencia = {
        "tras_reiniciar_el_flujo": {"mensajes_guardados": len(reinicio.todos()),
                                    "ventana_que_ve_el_agente": len(reinicio.messages)},
        "sesion_nueva_del_mismo_usuario": {
            "borrador": leer_borrador(memoria, usuario, otra_sesion),
            "preferencias": preferencias(memoria, usuario),
            "episodios_recuperados": [{"similitud": round(float(r["similitud"]), 3),
                                       "texto": r["texto"][:160]}
                                      for r in recuperar(memoria, usuario, pregunta_recuerdo, embedder)]},
        "otro_usuario": {
            "borrador": leer_borrador(memoria, "luis", otro_usuario_sesion),
            "preferencias": preferencias(memoria, "luis"),
            "episodios_recuperados": recuperar(memoria, "luis", pregunta_recuerdo, embedder)},
        "pregunta_usada_para_recuperar": pregunta_recuerdo,
    }
    print("mapa:", json.dumps(mapa, ensure_ascii=False)[:500])
    print("persistencia:", json.dumps(persistencia, ensure_ascii=False)[:700])

    informe = {
        "fase": 3, "rubricas": ["R13", "R14", "R15", "R16", "R17", "R18"],
        "modo": "real remoto (OpenAI y ViaCEP); NLI y embeddings reales locales; datos sintéticos",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo,
        "r16_chatbot_conversation_buffer_memory": {"turnos": r16,
                                                   "memoria_final": buffer.load_memory_variables({})["history"]},
        "r17_intencion_y_entidades": r17,
        "r18_conversacion_compleja": r18,
        "r13_mapa_de_memorias": mapa,
        "r14_r18_persistencia_y_aislamiento": persistencia,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("guardado en", salida)


if __name__ == "__main__":
    main()
