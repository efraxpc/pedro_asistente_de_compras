import json
import sqlite3

import pytest
from pydantic import ValidationError

from pedro.business import comparar
from pedro.catalog import abrir_escenario, crear_escenario, ofertas
from pedro.contracts import Oferta, RespuestaCompra, Solicitud
from pedro.verification import respuesta_local, verificar


@pytest.fixture
def escenario(tmp_path):
    return crear_escenario(tmp_path)


def test_fuente_semilla_y_escenario(escenario, tmp_path):
    meta = json.loads((escenario.ruta.parent / "manifest.json").read_text())
    assert meta["semilla"] == 20261107
    assert meta["recuentos"] == {"parts": 2640, "offers": 7920,
                                 "compatibility": 7920, "price_history": 47520}
    assert abrir_escenario(tmp_path, escenario.dataset_id) == escenario
    with sqlite3.connect(escenario.ruta) as db:
        assert db.execute("SELECT count(*) FROM offers WHERE part_id='PEC-01-0001'").fetchone()[0] == 3


def test_limites_empate_y_flete_unico():
    base = dict(dataset_id="d", producto_id="p", proveedor_nombre="x",
                precio_unitario_centavos=100, flete_centavos=20, stock=2, plazo_dias=7)
    a = Oferta(id="a", proveedor_id="B", **base)
    b = Oferta(id="b", proveedor_id="A", **base)
    solicitud = Solicitud(producto_id="p", cantidad=2, presupuesto_centavos=220, plazo_max_dias=7)
    alternativas = comparar(solicitud, [a, b])
    assert [x.oferta.id for x in alternativas] == ["b", "a"]
    assert all(x.cumple and x.total_centavos == 220 for x in alternativas)
    assert comparar(solicitud.model_copy(update={"presupuesto_centavos": 219}), [a])[0].motivos == ["presupuesto"]
    assert comparar(solicitud.model_copy(update={"cantidad": 3}), [a])[0].motivos == ["stock", "presupuesto"]
    assert comparar(solicitud.model_copy(update={"plazo_max_dias": 6}), [a])[0].motivos == ["plazo"]


def test_faltante_no_es_cero_y_json_invalido():
    assert Solicitud(producto_id="p").faltantes() == ["cantidad"]
    with pytest.raises(ValidationError):
        Solicitud.model_validate_json('{"producto_id":"p","cantidad":0}')
    with pytest.raises(ValidationError):
        RespuestaCompra.model_validate_json("no es json")


def test_comparar_sin_limites_opcionales():
    oferta = Oferta(dataset_id="d", id="a", producto_id="p", proveedor_id="A",
                    proveedor_nombre="x", precio_unitario_centavos=100,
                    flete_centavos=20, stock=2, plazo_dias=30)
    alternativa = comparar(Solicitud(producto_id="p", cantidad=2), [oferta])[0]
    assert alternativa.cumple and alternativa.total_centavos == 220


def test_verificador_rechaza_omisiones_y_dataset(escenario):
    solicitud = Solicitud(producto_id="PEC-01-0001", cantidad=2,
                         presupuesto_centavos=10_000_000, plazo_max_dias=60)
    respuesta = respuesta_local(escenario, solicitud)
    assert verificar(respuesta, escenario) == []
    assert len(respuesta.alternativas) == len(ofertas(escenario, solicitud.producto_id))
    assert "ofertas incompletas" in verificar(respuesta.model_copy(update={
        "alternativas": respuesta.alternativas[:-1]}), escenario)
    assert "evidencia incompleta" in verificar(respuesta.model_copy(update={
        "evidencias": respuesta.evidencias[:-1]}), escenario)
    assert verificar(respuesta.model_copy(update={"dataset_id": "ajeno"}), escenario) == ["dataset ajeno"]
    assert "ganador o total incorrecto" in verificar(respuesta.model_copy(update={
        "total_centavos": respuesta.total_centavos + 1}), escenario)
