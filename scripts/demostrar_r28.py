"""R28: la interfaz Streamlit conectada al agente final, conducida con AppTest.

Ejecuta app.py de verdad (sin navegador): escribe en el chat, cambia de vista y de conversación.
Requiere OPENAI_API_KEY. Usa una carpeta de datos propia para no tocar las conversaciones del
usuario, y habilita el índice de políticas guardado, que es propio y tiene manifiesto.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TURNOS = ["Necesito 2 unidades de PEC-01-0001 con plazo máximo de 7 días",
          "Ahora que sean 3 y mantén el plazo",
          "¿A qué ciudad corresponde el CEP 01001000?",
          "¿Se puede mandar en varias cajas?"]


def _mensajes(app) -> list[dict]:
    return [{"rol": m.name, "texto": m.markdown[0].value if m.markdown else ""}
            for m in app.chat_message]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--salida", type=Path, default=ROOT / "docs/trazas/r28_streamlit.json")
    salida = argumentos.parse_args().salida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sin ejecución remota")
    os.chdir(ROOT)
    os.environ["PEDRO_STORAGE"] = f"storage/evidencias/r28-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
    os.environ["PEDRO_TRUST_POLICY_INDEX"] = "true"
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    app.run()
    informe: dict = {
        "rubrica": "R28",
        "modo": "app.py ejecutada con streamlit.testing.v1.AppTest; agente real remoto (OpenAI, ViaCEP); "
                "NLI real local; índice de políticas cargado de disco",
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": os.getenv("PEDRO_MODEL", "gpt-4.1-mini"),
        "arranque": {"titulos": [t.value for t in app.title],
                     "excepciones": [str(e.value) for e in app.exception]},
    }
    chat = []
    for texto in TURNOS:
        app.chat_input[0].set_value(texto).run()
        respuesta = _mensajes(app)[-1]["texto"]
        chat.append({"usuario": texto, "pedro": respuesta,
                     "avisos": [w.value for w in app.warning] + [e.value for e in app.error]})
        print("chat |", texto, "->", respuesta.splitlines()[0][:110] if respuesta else "(vacío)")
    informe["vista_chat"] = {"turnos": chat, "mensajes_en_pantalla": len(_mensajes(app))}
    primera_sesion = app.session_state["sesion"]

    # Nuevo chat: misma app, sesión distinta y pantalla vacía.
    next(b for b in app.sidebar.button if b.label == "Nuevo chat").click().run()
    informe["nuevo_chat"] = {"sesion_distinta": app.session_state["sesion"] != primera_sesion,
                             "mensajes_en_pantalla": len(_mensajes(app))}
    # Reabrir la conversación anterior desde la barra lateral: el historial vuelve.
    next(b for b in app.sidebar.button if b.label.startswith(primera_sesion[:8])).click().run()
    reabierta = _mensajes(app)
    informe["conversacion_reabierta"] = {"mensajes_en_pantalla": len(reabierta),
                                         "primer_mensaje": reabierta[0]["texto"] if reabierta else None}
    print("nuevo chat:", informe["nuevo_chat"], "| reabierta:", len(reabierta), "mensajes")

    # Las otras dos vistas usan el mismo escenario y el mismo verificador.
    app.sidebar.button_group[0].set_value("Catálogo de piezas").run()
    informe["vista_catalogo"] = {"titulo": app.title[0].value,
                                 "resumen": [c.value for c in app.caption if "piezas" in c.value][-1:],
                                 "excepciones": [str(e.value) for e in app.exception]}
    app.sidebar.button_group[0].set_value("Comparación local").run()
    app.text_input[0].set_value("PEC-01-0001")
    app.number_input[0].set_value(3)
    next(b for b in app.button if b.label == "Comparar").click().run()
    informe["vista_comparacion"] = {"titulo": app.title[0].value,
                                    "resultado": [s.value for s in app.success],
                                    "avisos": [w.value for w in app.warning] + [e.value for e in app.error],
                                    "ofertas_mostradas": [len(d.value) for d in app.dataframe],
                                    "excepciones": [str(e.value) for e in app.exception]}
    print("catálogo:", informe["vista_catalogo"], "| comparación:", informe["vista_comparacion"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("guardado en", salida)


if __name__ == "__main__":
    main()
