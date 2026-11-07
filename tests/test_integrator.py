from compraslab.agent import crear_integrador
from compraslab.business import comparar_ofertas
from compraslab.data import crear_catalogo, ofertas_producto
from compraslab.memory import HistorialSQLite, nueva_sesion
from compraslab.schemas import Evidencia, RespuestaCompra, SolicitudCompra
from compraslab.verification import verificar
from compraslab.agent import renderizar


class ExecutorGuionado:
    """Prueba el control de publicación, no la calidad de un modelo real."""
    def __init__(self, salidas):
        self.salidas = iter(salidas)
        self.llamadas = 0

    def invoke(self, dato, config=None):
        self.llamadas += 1
        return {"output": next(self.salidas)}


def respuesta_valida(catalogo):
    solicitud = SolicitudCompra(producto_id="PROD-003", cantidad=1,
                               presupuesto_centavos=10_000_000, plazo_max_dias=30)
    alternativas = comparar_ofertas(solicitud, ofertas_producto(catalogo, "PROD-003"))
    ganador = alternativas[0]
    return RespuestaCompra(estado="recomendacion", mensaje="propuesta",
        dataset_id=catalogo.dataset_id, solicitud=solicitud, producto_id="PROD-003",
        proveedor_id=ganador.oferta.proveedor_id, total_centavos=ganador.total_centavos,
        alternativas=alternativas,
        evidencias=[Evidencia(tipo="catalogo", fuente_id=a.oferta.id,
                              dataset_id=catalogo.dataset_id, texto="oferta") for a in alternativas])


def test_correccion_interna_no_se_guarda(tmp_path):
    catalogo = crear_catalogo(tmp_path / "catalogos", cantidad=3, semilla=1)
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "u1", catalogo.dataset_id)
    valida = respuesta_valida(catalogo)
    invalida = valida.model_copy(update={"total_centavos": 1})
    executor = ExecutorGuionado([invalida.model_dump_json(), valida.model_dump_json()])
    integrador = crear_integrador(executor, catalogo, memoria, nli=lambda _: True)
    salida = integrador.invoke({"input": "Quiero PROD-003"},
        config={"configurable": {"user_id": "u1", "session_id": sesion}})
    assert executor.llamadas == 2
    assert "R$" in salida.content
    mensajes = HistorialSQLite(memoria, sesion, "u1").messages
    assert len(mensajes) == 2
    assert "R$" in mensajes[-1].content


def test_sin_nli_publica_respuesta_limitada(tmp_path):
    catalogo = crear_catalogo(tmp_path / "catalogos", cantidad=3, semilla=1)
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "u1", catalogo.dataset_id)
    valida = respuesta_valida(catalogo)
    executor = ExecutorGuionado([valida.model_dump_json()] * 2)
    integrador = crear_integrador(executor, catalogo, memoria)
    salida = integrador.invoke({"input": "Quiero PROD-003"},
        config={"configurable": {"user_id": "u1", "session_id": sesion}})
    assert executor.llamadas == 2
    assert "No puedo confirmar" in salida.content


def test_sin_oferta_explica_descartes_verificados(tmp_path):
    catalogo = crear_catalogo(tmp_path / "catalogos", cantidad=3, semilla=1)
    solicitud = SolicitudCompra(producto_id="PROD-003", cantidad=1000,
                               presupuesto_centavos=1, plazo_max_dias=0)
    alternativas = comparar_ofertas(solicitud, ofertas_producto(catalogo, "PROD-003"))
    respuesta = RespuestaCompra(estado="sin_oferta", mensaje="texto libre no publicado",
        dataset_id=catalogo.dataset_id, solicitud=solicitud, producto_id="PROD-003",
        alternativas=alternativas)
    assert verificar(respuesta, catalogo).aprobado
    assert "descartada por" in renderizar(respuesta)
    assert "texto libre" not in renderizar(respuesta)
    assert not verificar(respuesta.model_copy(update={"alternativas": alternativas[:1]}), catalogo).aprobado
