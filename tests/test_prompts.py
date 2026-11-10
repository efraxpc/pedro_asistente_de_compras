import pytest

from pedro.chains import PROMPT, crear_lcel
from pedro.prompts import (EJEMPLOS_ACCIONES, EJEMPLOS_EXTRACCION, PLANTILLA_AGENTE,
                           PLANTILLA_EXTRACCION, PLANTILLA_EXTRACCION_COT,
                           PLANTILLA_EXTRACCION_FEWSHOT)


def test_plantilla_de_extraccion_declara_sus_variables_y_se_reutiliza():
    assert sorted(PLANTILLA_EXTRACCION.input_variables) == ["formato", "texto"]
    assert PROMPT is PLANTILLA_EXTRACCION
    assert crear_lcel(lambda prompt: "{}").first.messages == PLANTILLA_EXTRACCION.messages
    sistema, humano = PLANTILLA_EXTRACCION.format_messages(
        texto="Compara 2 unidades de PEC-01-0001", formato="JSON")
    assert (sistema.type, humano.type) == ("system", "human")
    assert humano.content == "Compara 2 unidades de PEC-01-0001"
    assert "PEC-01-0001" not in sistema.content


def test_plantilla_del_agente_admite_cualquier_escenario():
    assert {"dataset_id", "ejemplos", "formato", "input", "agent_scratchpad"} <= set(
        PLANTILLA_AGENTE.input_variables)
    for dataset_id in ("escenario-a", "escenario-b"):
        sistema = PLANTILLA_AGENTE.format_messages(
            dataset_id=dataset_id, ejemplos=EJEMPLOS_ACCIONES, formato="JSON",
            input="hola", agent_scratchpad=[])[0]
        assert dataset_id in sistema.content
        assert all(f"{parte}:" in sistema.content
                   for parte in ("Persona", "Tarea", "Contexto", "Formato"))


@pytest.mark.parametrize("faltante", ["texto", "formato"])
def test_plantilla_falla_si_falta_una_variable(faltante):
    valores = {"texto": "Necesito un filtro", "formato": "JSON"}
    del valores[faltante]
    with pytest.raises(KeyError):
        PLANTILLA_EXTRACCION.format_messages(**valores)


def test_few_shot_inserta_los_ejemplos_como_turnos_resueltos():
    mensajes = PLANTILLA_EXTRACCION_FEWSHOT.format_messages(texto="Necesito un filtro", formato="JSON")
    tipos = [m.type for m in mensajes]
    assert tipos == ["system"] + ["human", "ai"] * len(EJEMPLOS_EXTRACCION) + ["human"]
    assert mensajes[-1].content == "Necesito un filtro"
    assert all("razonamiento" not in m.content for m in mensajes if m.type == "ai")


def test_cot_pone_el_razonamiento_antes_que_los_datos():
    mensajes = PLANTILLA_EXTRACCION_COT.format_messages(texto="Necesito un filtro", formato="JSON")
    respuestas = [m.content for m in mensajes if m.type == "ai"]
    assert len(respuestas) == len(EJEMPLOS_EXTRACCION)
    assert all(r.index("razonamiento") < r.index("solicitud") for r in respuestas)
    assert "paso a paso" in mensajes[0].content


def test_los_ejemplos_ensenan_que_un_dato_ausente_no_es_cero():
    sin_cantidad = next(e for e in EJEMPLOS_EXTRACCION if e["faltantes"] == ["cantidad"])
    assert "cantidad" not in sin_cantidad["solicitud"]
