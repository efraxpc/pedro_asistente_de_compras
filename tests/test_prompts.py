import pytest

from pedro.chains import PROMPT, crear_lcel
from pedro.prompts import EJEMPLOS_ACCIONES, PLANTILLA_AGENTE, PLANTILLA_EXTRACCION


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
