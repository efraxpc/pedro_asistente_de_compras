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


def test_la_comparacion_se_ancla_al_calculo_de_la_herramienta(tmp_path):
    from pedro.catalog import crear_escenario
    from pedro.contracts import Solicitud
    from pedro.verification import anclar_recomendacion, respuesta_local, verificar

    escenario = crear_escenario(tmp_path / "catalogos")
    solicitud = Solicitud(producto_id="PEC-01-0001", cantidad=5)
    calculada = respuesta_local(escenario, solicitud)
    observacion = ("comparar_ofertas", calculada.model_dump(mode="json"))

    # El modelo copia mal el ganador y el total.
    propuesta = calculada.model_copy(deep=True)
    propuesta.proveedor_id, propuesta.total_centavos = "INT-06", 1
    assert "ganador o total incorrecto" in verificar(propuesta, escenario)
    informe = anclar_recomendacion(propuesta, [observacion])
    assert informe == {"estado": "anclada", "campos_corregidos": ["proveedor_id", "total_centavos"]}
    assert verificar(propuesta, escenario) == []
    assert (propuesta.proveedor_id, propuesta.total_centavos) == (
        calculada.proveedor_id, calculada.total_centavos)

    # Sin un cálculo para esa misma solicitud no se corrige nada y la verificación lo rechaza.
    otra = calculada.model_copy(deep=True)
    otra.solicitud.cantidad, otra.proveedor_id = 6, "INT-06"
    assert anclar_recomendacion(otra, [observacion]) == {"estado": "sin_calculo_para_esa_solicitud"}
    assert verificar(otra, escenario) != []
    assert anclar_recomendacion(propuesta, []) == {"estado": "sin_calculo_para_esa_solicitud"}


def test_el_pedido_minimo_descarta_una_oferta_aunque_sea_la_mas_barata(tmp_path):
    from pedro.agent import renderizar
    from pedro.catalog import crear_escenario, ofertas
    from pedro.contracts import Solicitud
    from pedro.verification import respuesta_local, verificar

    escenario = crear_escenario(tmp_path / "catalogos")
    por_proveedor = {o.proveedor_id: o for o in ofertas(escenario, "PEC-01-0001")}
    assert (por_proveedor["BR-06"].pedido_minimo, por_proveedor["INT-06"].pedido_minimo) == (5, 1)
    assert por_proveedor["BR-06"].nacional and not por_proveedor["INT-06"].nacional

    dos = respuesta_local(escenario, Solicitud(producto_id="PEC-01-0001", cantidad=2))
    assert dos.proveedor_id == "INT-06" and verificar(dos, escenario) == []
    centro = next(a for a in dos.alternativas if a.oferta.proveedor_id == "BR-06")
    assert not centro.cumple and centro.motivos == ["pedido_minimo"]
    assert "CentroPeças (nacional)" in renderizar(dos)
    assert "descartada por pedido mínimo (5 unidades)" in renderizar(dos)

    cinco = respuesta_local(escenario, Solicitud(producto_id="PEC-01-0001", cantidad=5))
    assert cinco.proveedor_id == "BR-06" and cinco.total_centavos == 5 * 143892 + 8523


def test_la_preferencia_de_origen_ordena_las_ofertas_validas_y_se_explica(tmp_path):
    from pedro.agent import renderizar
    from pedro.business import origen_preferido
    from pedro.catalog import crear_escenario
    from pedro.contracts import Solicitud
    from pedro.verification import respuesta_local, verificar

    assert origen_preferido({"proveedor": "nacionales"}) == "nacional"
    assert origen_preferido({"proveedores": "prefiero internacionales"}) == "internacional"
    assert origen_preferido({"color": "azul"}) is None and origen_preferido({}) is None

    escenario = crear_escenario(tmp_path / "catalogos")
    base = Solicitud(producto_id="PEC-01-0001", cantidad=5)
    sin_preferencia = respuesta_local(escenario, base)
    internacional = respuesta_local(escenario, base.model_copy(update={"origen_preferido": "internacional"}))
    # Sin preferencia gana la más barata; con ella, la del origen preferido aunque cueste más.
    assert sin_preferencia.proveedor_id == "BR-06" and internacional.proveedor_id == "INT-06"
    assert internacional.total_centavos > sin_preferencia.total_centavos
    assert verificar(internacional, escenario) == []
    texto = renderizar(internacional)
    assert "Se aplicó tu preferencia por proveedores internacionales." in texto
    assert "Sin ella, la más barata sería CentroPeças" in texto
    assert "preferencia" not in renderizar(sin_preferencia)
    # La preferencia nunca hace ganar a una oferta que no cumple.
    solo_dos = respuesta_local(escenario, Solicitud(producto_id="PEC-01-0001", cantidad=2,
                                                    origen_preferido="nacional"))
    assert solo_dos.proveedor_id == "INT-06"
