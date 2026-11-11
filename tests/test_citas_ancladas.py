import json
from types import SimpleNamespace

import pytest

from pedro.agent import Traza, crear_flujo
from pedro.catalog import crear_escenario
from pedro.contracts import Evidencia, RespuestaCompra, Solicitud
from pedro.memory import nueva_sesion
from pedro.policy_demo import crear_indice_demo
from pedro.verification import anclar_cita, anclar_citas
from tests.test_policy_demo import EmbeddingsPrueba

FRAGMENTO = ("El daño visible al abrir la caja debe notificarse dentro de **7 días corridos** "
             "desde la entrega simulada. La notificación debe incluir una fotografía de la caja.")
CITA_CASI_LITERAL = ("El daño visible al abrir la caja debe notificarse dentro de 7 días corridos "
                     "desde la entrega simulada...")


def test_cita_casi_literal_se_ancla_al_texto_del_fragmento():
    tramo, cobertura = anclar_cita(CITA_CASI_LITERAL, FRAGMENTO)
    assert tramo is not None and tramo in FRAGMENTO
    assert "**7 días corridos**" in tramo and cobertura >= 0.8


@pytest.mark.parametrize("cita", [
    "El daño visible puede notificarse en cualquier momento y sin fotografías de la caja.",
    "La garantía cubre doce meses de uso doméstico continuo del compresor.",
    "7 días",
])
def test_cita_inventada_o_demasiado_corta_no_se_ancla(cita):
    assert anclar_cita(cita, FRAGMENTO)[0] is None


def test_anclar_citas_informa_el_estado_de_cada_fuente():
    observaciones = [("consultar_politicas", {"fragmentos": [
        {"fuente_id": "A", "texto": FRAGMENTO}, {"fuente_id": "B", "texto": FRAGMENTO}]})]
    respuesta = RespuestaCompra(estado="politica", dataset_id="d", solicitud=Solicitud(), evidencias=[
        Evidencia(tipo="politica", fuente_id="A", texto=CITA_CASI_LITERAL),
        Evidencia(tipo="politica", fuente_id="B", texto=""),
        Evidencia(tipo="politica", fuente_id="A", texto="Texto que la fuente no contiene en absoluto."),
        Evidencia(tipo="politica", fuente_id="Z", texto=FRAGMENTO)])
    estados = [c["estado"] for c in anclar_citas(respuesta, observaciones)]
    assert estados == ["reanclada", "por_identificador", "rechazada", "fuente_no_recuperada"]
    assert respuesta.evidencias[0].texto in FRAGMENTO
    assert respuesta.evidencias[1].texto == FRAGMENTO


def _chat(tmp_path, monkeypatch, cita, etiqueta_nli):
    import pedro.agent as modulo

    (tmp_path / "devoluciones.md").write_text(
        "# DEMOSTRACIÓN T15\n\n**Versión:** 1.1\n\ncorpus sintético\n\n## Regla\n" + FRAGMENTO + "\n",
        encoding="utf-8")
    for nombre in ("garantia", "entrega"):
        (tmp_path / f"{nombre}.md").write_text(
            f"# DEMOSTRACIÓN T15\n\n**Versión:** 1.1\n\ncorpus sintético\n\n## Regla\n{nombre} {nombre}.\n",
            encoding="utf-8")
    indice = crear_indice_demo(tmp_path, EmbeddingsPrueba())
    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    fuente_id = next(i for i, d in indice.docstore._dict.items() if FRAGMENTO[:40] in d.page_content)
    literal = indice.docstore.search(fuente_id).page_content
    observacion = json.dumps({"fragmentos": [{"fuente_id": fuente_id, "texto": literal}]})
    # El modelo copia mal el identificador del escenario; eso no debe impedir publicar.
    respuesta = RespuestaCompra(
        estado="politica", dataset_id="identificador-mal-copiado", solicitud=Solicitud(),
        mensaje="El daño visible se notifica en 7 días corridos.",
        evidencias=[Evidencia(tipo="politica", fuente_id=fuente_id, texto=cita)])

    class Executor:
        def invoke(self, entrada, config):
            return {"output": respuesta.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_politicas"), observacion)]}

    class NLI:
        def clasificar(self, premisa, hipotesis):
            return etiqueta_nli

    monkeypatch.setattr(modulo, "crear_agente", lambda *args, **kwargs: Executor())
    traza = Traza()
    flujo = crear_flujo(escenario, memoria, llm=object(), clasificador=NLI(), indice=indice,
                        traza=traza)
    salida = flujo.invoke({"input": "¿Qué dice la política de devolución sobre daños?"},
                          config={"configurable": {"user_id": "ana", "session_id": sesion}})
    estados = [c["estado"] for e in traza.eventos if e["evento"] == "citas_ancladas"
               for c in e["citas"]]
    return salida.content, estados, fuente_id


def test_chat_publica_resumen_cuando_la_cita_se_reancla_y_hay_entailment(tmp_path, monkeypatch):
    texto, estados, fuente_id = _chat(tmp_path, monkeypatch, CITA_CASI_LITERAL, "entailment")
    assert "El daño visible se notifica en 7 días corridos." in texto and fuente_id in texto
    assert estados == ["reanclada"]


def test_chat_degrada_a_cita_textual_si_el_resumen_no_tiene_entailment(tmp_path, monkeypatch):
    texto, estados, fuente_id = _chat(tmp_path, monkeypatch, CITA_CASI_LITERAL, "neutral")
    assert "cito el texto literal" in texto and "**7 días corridos**" in texto
    assert "El daño visible se notifica en 7 días corridos." not in texto
    assert fuente_id in texto and estados == ["reanclada", "reanclada"]


def test_chat_no_publica_una_cita_inventada(tmp_path, monkeypatch):
    texto, estados, _ = _chat(tmp_path, monkeypatch,
                              "El daño visible puede notificarse sin plazo y sin fotografías.",
                              "entailment")
    assert texto.startswith("No pude verificar la respuesta sobre políticas")
    assert estados == ["rechazada", "rechazada"]
