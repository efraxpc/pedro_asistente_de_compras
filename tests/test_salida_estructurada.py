import json

import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import RunnableLambda

from pedro.chains import crear_lcel, crear_lcel_robusta
from pedro.laboratorio import CORRECTA, SALIDAS_ROTAS, SOLICITUD, ensayar

REPARADOR = RunnableLambda(lambda prompt: json.dumps(CORRECTA))


def test_cada_salida_rota_la_resuelve_la_capa_prevista():
    informe = ensayar(REPARADOR)
    assert [(c["caso"], c["capa_observada"]) for c in informe] == [
        (nombre, capa) for nombre, (_, capa) in SALIDAS_ROTAS.items()]
    assert all(c["reparaciones"] <= 1 for c in informe)


def test_la_reparacion_recibe_solicitud_salida_y_error():
    visto = {}

    def reparador(prompt):
        visto["humano"] = prompt.to_messages()[-1].content
        return json.dumps(CORRECTA)

    cadena = crear_lcel_robusta(RunnableLambda(lambda _: SALIDAS_ROTAS["cantidad negativa"][0]),
                                RunnableLambda(reparador))
    assert cadena.invoke({"texto": SOLICITUD}).solicitud.cantidad == 2
    assert SOLICITUD in visto["humano"] and '"cantidad": -2' in visto["humano"]
    assert "greater than 0" in visto["humano"]


def test_una_reparacion_que_tambien_falla_no_se_publica():
    cadena = crear_lcel_robusta(RunnableLambda(lambda _: "no es JSON"),
                                RunnableLambda(lambda _: "sigue sin ser JSON"))
    with pytest.raises(OutputParserException):
        cadena.invoke({"texto": SOLICITUD})


def test_los_faltantes_los_calcula_el_codigo_no_el_modelo():
    salida = SALIDAS_ROTAS["faltantes mal declarados"][0]
    assert json.loads(salida)["faltantes"] == []
    cadena = crear_lcel_robusta(RunnableLambda(lambda _: salida), REPARADOR)
    assert cadena.invoke({"texto": SOLICITUD}).faltantes == ["cantidad"]


def test_el_parser_solo_pierde_un_dato_en_silencio_y_la_cadena_robusta_lo_evita():
    truncada = SALIDAS_ROTAS["JSON truncado"][0]
    with pytest.raises(ValueError):
        json.loads(truncada)
    simple = crear_lcel(RunnableLambda(lambda _: truncada)).invoke({"texto": SOLICITUD})
    assert simple.solicitud.plazo_max_dias is None  # el plazo de 7 días desapareció sin error
    robusta = crear_lcel_robusta(RunnableLambda(lambda _: truncada), REPARADOR)
    assert robusta.invoke({"texto": SOLICITUD}).solicitud.plazo_max_dias == 7
