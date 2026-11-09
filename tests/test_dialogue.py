import pytest

from pedro.agent import crear_flujo
from pedro.catalog import crear_escenario
from pedro.dialogue import EstadoCompra, interpretar_compra
from pedro.memory import leer_borrador, nueva_sesion


@pytest.fixture
def contexto(tmp_path):
    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    flujo = crear_flujo(escenario, memoria)

    def preguntar(texto, session_id=sesion, user_id="ana"):
        return str(flujo.invoke({"input": texto}, config={"configurable": {
            "user_id": user_id, "session_id": session_id}}).content)

    return escenario, memoria, sesion, preguntar


def test_pide_solo_cantidad_y_compara_sin_limites(contexto):
    escenario, memoria, sesion, preguntar = contexto
    pregunta = preguntar("Compara PEC-01-0001")
    assert "¿Cuántas unidades" in pregunta
    assert "presupuesto_centavos" not in pregunta
    respuesta = preguntar("2, por favor")
    assert "Fuentes:" in respuesta
    assert "PEC-01-0001" in leer_borrador(memoria, "ana", sesion)["solicitud"]["producto_id"]
    solicitud = EstadoCompra.model_validate(leer_borrador(memoria, "ana", sesion)).solicitud
    assert solicitud.cantidad == 2
    assert solicitud.presupuesto_centavos is None
    assert solicitud.plazo_max_dias is None
    assert respuesta != preguntar("ahora 3 unidades")
    assert leer_borrador(memoria, "ana", sesion)["solicitud"]["cantidad"] == 3
    preguntar("cambia la cantidad a dos")
    assert leer_borrador(memoria, "ana", sesion)["solicitud"]["cantidad"] == 2


def test_correccion_conserva_filtros_explicitos_y_permita_quitarlos(contexto):
    _, memoria, sesion, preguntar = contexto
    respuesta = preguntar("Compara 2 unidades de PEC-01-0001 con presupuesto R$ 1.000,00 y plazo 7 días")
    assert "Fuentes:" in respuesta
    preguntar("Ahora 3 unidades")
    solicitud = EstadoCompra.model_validate(leer_borrador(memoria, "ana", sesion)).solicitud
    assert (solicitud.cantidad, solicitud.presupuesto_centavos, solicitud.plazo_max_dias) == (3, 100000, 7)
    preguntar("Sin presupuesto y sin plazo")
    solicitud = EstadoCompra.model_validate(leer_borrador(memoria, "ana", sesion)).solicitud
    assert solicitud.presupuesto_centavos is None
    assert solicitud.plazo_max_dias is None


def test_borrador_aislado_por_sesion_y_usuario(contexto):
    escenario, memoria, sesion, preguntar = contexto
    preguntar("Compara PEC-01-0001")
    otra = nueva_sesion(memoria, "ana", escenario.dataset_id)
    assert "¿Qué pieza" in preguntar("Compara", otra)
    assert leer_borrador(memoria, "ana", otra)["solicitud"]["producto_id"] is None
    with pytest.raises(ValueError, match="sesión ajena"):
        leer_borrador(memoria, "otra", sesion)


def test_cep_no_reutiliza_borrador_de_compra(contexto):
    escenario, memoria, sesion, preguntar = contexto
    preguntar("Compara PEC-01-0001")
    previo = EstadoCompra.model_validate(leer_borrador(memoria, "ana", sesion))
    assert interpretar_compra(escenario, previo, "Consulta el CEP 01001000") is None
