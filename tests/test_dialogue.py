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


@pytest.mark.parametrize("mensaje, cantidad", [
    ("Ahora que sean 3 y mantén el plazo", 3),
    ("Mejor 4", 4),
    ("cambia a 5", 5),
    ("que sean seis", 6),
    ("ahora media docena", 6),
])
def test_cambio_de_cantidad_dicho_de_pasada_conserva_el_plazo(contexto, mensaje, cantidad):
    escenario, _, _, _ = contexto
    previo, _ = interpretar_compra(escenario, None, "Necesito 2 unidades de PEC-01-0001 con plazo 7 días")
    estado, aclaracion = interpretar_compra(escenario, previo, mensaje)
    assert aclaracion is None
    assert (estado.solicitud.cantidad, estado.solicitud.plazo_max_dias) == (cantidad, 7)


def test_cambiar_el_plazo_no_se_confunde_con_la_cantidad(contexto):
    escenario, _, _, _ = contexto
    previo, _ = interpretar_compra(escenario, None, "Necesito 2 unidades de PEC-01-0001")
    estado, _ = interpretar_compra(escenario, previo, "mejor 10 días de plazo")
    assert (estado.solicitud.cantidad, estado.solicitud.plazo_max_dias) == (2, 10)


@pytest.mark.parametrize("mensaje", [
    "¿Cómo se comprueba la compatibilidad eléctrica antes de instalar una pieza?",
    "¿Qué cubre la garantía de una pieza?",
    "Prefiero proveedores nacionales, recuérdalo",
    "¿A qué ciudad corresponde el CEP 01001000?",
])
def test_preguntas_que_no_son_compra_no_tocan_el_borrador(contexto, mensaje):
    escenario, _, _, _ = contexto
    previo, _ = interpretar_compra(escenario, None, "Necesito 2 unidades de PEC-01-0001")
    assert interpretar_compra(escenario, previo, mensaje) is None


def test_preferencia_se_confirma_solo_si_la_herramienta_la_guardo(tmp_path):
    from pedro.contracts import RespuestaCompra, Solicitud
    from pedro.verification import anclar_preferencia, verificar

    escenario = crear_escenario(tmp_path / "catalogos")
    respuesta = RespuestaCompra(estado="preferencia", dataset_id=escenario.dataset_id,
                                solicitud=Solicitud(), mensaje="Hecho, y además te recomiendo BR-06.")
    guardada = ("guardar_preferencia", {"estado": "ok", "clave": "proveedor", "valor": "nacionales"})
    assert verificar(respuesta, escenario, observaciones=[]) == ["preferencia no guardada"]
    assert anclar_preferencia(respuesta, [guardada])["estado"] == "anclada"
    assert respuesta.mensaje == "Guardé tu preferencia: proveedor = nacionales."
    assert verificar(respuesta, escenario, observaciones=[guardada]) == []
    rechazada = ("guardar_preferencia", {"estado": "invalido", "error": "sin petición explícita"})
    assert verificar(respuesta, escenario, observaciones=[rechazada]) == ["preferencia no guardada"]
