import httpx

from compraslab.business import comparar_ofertas
from compraslab.integrations import consultar_cep
from compraslab.schemas import Oferta, SolicitudCompra


def oferta(id_, proveedor, precio, flete, stock, plazo):
    return Oferta(dataset_id="d", id=id_, producto_id="PROD-001",
        proveedor_id=proveedor, proveedor_nombre=proveedor,
        precio_unitario_centavos=precio, flete_centavos=flete,
        stock=stock, plazo_dias=plazo)


def test_limites_inclusivos_flete_unico_y_orden():
    solicitud = SolicitudCompra(producto_id="PROD-001", cantidad=2,
                               presupuesto_centavos=210, plazo_max_dias=7)
    alternativas = comparar_ofertas(solicitud, [
        oferta("a", "B", 100, 10, 2, 7),
        oferta("b", "A", 100, 10, 2, 7),
        oferta("c", "C", 100, 11, 2, 7),
        oferta("d", "D", 100, 0, 1, 1),
    ])
    assert [a.oferta.proveedor_id for a in alternativas[:2]] == ["A", "B"]
    assert alternativas[0].total_centavos == 210  # flete cobrado una vez
    assert alternativas[0].cumple  # stock, presupuesto y plazo exactos
    assert {a.oferta.id: a.motivos for a in alternativas}["c"] == ["presupuesto"]
    assert {a.oferta.id: a.motivos for a in alternativas}["d"] == ["stock"]


def test_viacep_invalido_inexistente_y_timeout():
    assert consultar_cep("01001").estado == "invalido"
    inexistente = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"erro": True})))
    assert consultar_cep("99999999", cliente=inexistente).estado == "no_encontrado"
    def timeout(request):
        raise httpx.ReadTimeout("timeout", request=request)
    caido = httpx.Client(transport=httpx.MockTransport(timeout))
    assert consultar_cep("01001000", cliente=caido).estado == "indisponible"
