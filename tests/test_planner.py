import json
from types import SimpleNamespace

import pytest
from langchain_core.runnables import RunnableLambda

from pedro.agent import Traza, crear_flujo
from pedro.catalog import crear_escenario
from pedro.contracts import Evidencia, RespuestaCompra, Solicitud
from pedro.memory import Historial, nueva_sesion
from pedro.planner import (PlanTurno, intenciones_detectadas, planificar_turno, validar_plan)
from pedro.verification import respuesta_local

MIXTO = "Compara 2 unidades de PEC-01-0001 con plazo de 7 días y confirma el CEP 01001000"


def _plan(*pares):
    return PlanTurno.model_validate({"peticiones": [{"tipo": t, "peticion": p} for t, p in pares]})


def _modelo(plan: PlanTurno):
    return RunnableLambda(lambda _: plan.model_dump_json())


def test_solo_se_planifica_si_hay_senales_de_varias_intenciones():
    assert intenciones_detectadas(MIXTO) == {"compra", "cep"}
    assert intenciones_detectadas("Compara 2 unidades de PEC-01-0001") == {"compra"}
    llamado = []
    modelo = RunnableLambda(lambda _: llamado.append(1) or "{}")
    assert planificar_turno("Compara 2 unidades de PEC-01-0001", modelo) is None
    assert llamado == []


def test_un_plan_valido_devuelve_las_peticiones_en_orden():
    plan = _plan(("compra", "Compara 2 unidades de PEC-01-0001 con plazo de 7 días"),
                 ("cep", "Confirma el CEP 01001000"))
    peticiones = planificar_turno(MIXTO, _modelo(plan))
    assert [p.tipo for p in peticiones] == ["compra", "cep"]


@pytest.mark.parametrize("plan, motivo", [
    (_plan(("compra", "Compara 5 unidades de PEC-01-0001"), ("cep", "Confirma el CEP 01001000")),
     "añade datos"),
    (_plan(("compra", "Compara 2 unidades de PEC-09-0009"), ("cep", "Confirma el CEP 01001000")),
     "añade datos"),
    (_plan(("compra", "Compara 2 unidades de PEC-01-0001"), ("compra", "Compara PEC-01-0001")),
     "repite"),
    (_plan(("compra", "Compara 2 unidades de PEC-01-0001"), ("politica", "Cuéntame algo")),
     "no lo parece"),
])
def test_un_plan_que_inventa_o_no_encaja_se_descarta(plan, motivo):
    with pytest.raises(ValueError, match=motivo):
        validar_plan(plan, MIXTO)
    assert planificar_turno(MIXTO, _modelo(plan)) is None


def test_un_plan_ilegible_o_de_una_peticion_equivale_a_no_planificar():
    assert planificar_turno(MIXTO, RunnableLambda(lambda _: "no es JSON")) is None
    assert planificar_turno(MIXTO, _modelo(_plan(("compra", "Compara 2 unidades de PEC-01-0001")))) is None
    assert planificar_turno(MIXTO, None) is None


def test_el_flujo_responde_cada_peticion_con_su_propia_verificacion(tmp_path, monkeypatch):
    import pedro.agent as modulo

    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    compra = respuesta_local(escenario, Solicitud(producto_id="PEC-01-0001", cantidad=2, plazo_max_dias=7))
    cep = RespuestaCompra(estado="cep", dataset_id=escenario.dataset_id, solicitud=Solicitud(cep="01001000"))
    plan = _plan(("compra", "Compara 2 unidades de PEC-01-0001 con plazo de 7 días"),
                 ("cep", "Confirma el CEP 01001000"))
    vistos = []

    class Executor:
        def invoke(self, entrada, config):
            vistos.append(entrada["input"].splitlines()[0])
            if "CEP" in entrada["input"]:
                return {"output": cep.model_dump_json(), "intermediate_steps": [
                    (SimpleNamespace(tool="consultar_cep"), json.dumps(
                        {"estado": "ok", "cep": "01001000", "cidade": "São Paulo", "uf": "SP",
                         "modo": "simulado"}))]}
            return {"output": compra.model_dump_json(), "intermediate_steps": []}

    class NLI:
        def clasificar(self, premisa, hipotesis):
            return "entailment"

    class Vectores:
        modelo, version = "test", "1"

        def embed(self, texto):
            return [1.0]

    monkeypatch.setattr(modulo, "crear_agente", lambda *args, **kwargs: Executor())
    monkeypatch.setattr(modulo, "FastEmbedder", Vectores)
    traza = Traza()
    flujo = crear_flujo(escenario, memoria, llm=_modelo(plan), clasificador=NLI(), traza=traza)
    salida = flujo.invoke({"input": MIXTO}, config={"configurable": {
        "user_id": "ana", "session_id": sesion}}).content
    assert vistos == ["Compara 2 unidades de PEC-01-0001 con plazo de 7 días", "Confirma el CEP 01001000"]
    assert "Tu mensaje tenía 2 peticiones" in salida
    assert "R$ 2.963,07" in salida and "São Paulo/SP" in salida
    assert [e["evento"] for e in traza.eventos if e["evento"] in ("plan", "verificacion")] == [
        "plan", "verificacion", "verificacion"]
    mensajes = Historial(memoria, "ana", sesion).todos()
    assert [m.type for m in mensajes] == ["human", "ai"] and mensajes[0].content == MIXTO
