import json

import httpx
import pytest

from compraslab.data import buscar_productos, crear_catalogo, listar_productos, ofertas_producto
from compraslab.query import text_to_query


def test_importa_productos_dummyjson_y_guarda_instantanea(tmp_path):
    def responder(request):
        assert request.url.path == "/products"
        assert request.url.params["limit"] == "0"
        return httpx.Response(200, json={"products": [
            {"id": 12, "title": "Monitor Demo", "sku": "MON-12", "price": 99.99, "stock": 4},
            {"id": 13, "title": "Teclado Demo", "sku": "TEC-13", "price": 29.99, "stock": 8},
        ]})

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        catalogo = crear_catalogo(tmp_path, modo="dummyjson", cantidad=1,
                                  semilla=42, cliente=cliente)

    productos = buscar_productos(catalogo, "Monitor")
    assert [(p.id, p.nombre, p.modelo) for p in productos] == [
        ("PROD-012", "Monitor Demo", "MON-12")]
    assert len(ofertas_producto(catalogo, "PROD-012")) == 3
    assert text_to_query(catalogo, "ofertas PROD-012").estado == "ok"
    assert len(listar_productos(catalogo)) == 1
    assert buscar_productos(catalogo, "Teclado") == []
    manifiesto = json.loads((tmp_path / catalogo.dataset_id / "manifest.json").read_text())
    assert manifiesto["fuente_productos"] == "https://dummyjson.com/products"
    assert manifiesto["ofertas"] == "simuladas"
    assert manifiesto["cantidad_productos"] == 1


def test_dummyjson_vacio_no_crea_escenario(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"products": []}))) as cliente:
        with pytest.raises(ValueError, match="no devolvió productos"):
            crear_catalogo(tmp_path, modo="dummyjson", cliente=cliente)
    assert not tmp_path.exists() or not list(tmp_path.iterdir())
