from pathlib import Path

import pytest

from compraslab.business import comparar_ofertas, formatar_brl
from compraslab.data import crear_catalogo, buscar_productos, listar_productos, ofertas_producto
from compraslab.memory import guardar_preferencia, nueva_sesion, preferencias
from compraslab.schemas import Evidencia, Oferta, RespuestaCompra, SolicitudCompra
from compraslab.verification import verificar


def test_regla_referencia_suministrada_en_prompt():
    # Fixture derivada de la solicitud, no reemplaza el kit original.
    ofertas = [
        Oferta(dataset_id="ref", id="a", producto_id="PROD-003", proveedor_id="A",
               proveedor_nombre="Demo A", precio_unitario_centavos=48000,
               flete_centavos=20000, stock=30, plazo_dias=12),
        Oferta(dataset_id="ref", id="b", producto_id="PROD-003", proveedor_id="B",
               proveedor_nombre="Demo B", precio_unitario_centavos=52000,
               flete_centavos=15000, stock=25, plazo_dias=5),
        Oferta(dataset_id="ref", id="c", producto_id="PROD-003", proveedor_id="C",
               proveedor_nombre="Demo C", precio_unitario_centavos=50000,
               flete_centavos=10000, stock=10, plazo_dias=3),
    ]
    solicitud = SolicitudCompra(producto_id="PROD-003", cantidad=20,
                               presupuesto_centavos=1200000, plazo_max_dias=7)
    alternativas = comparar_ofertas(solicitud, ofertas)
    assert alternativas[0].oferta.proveedor_nombre == "Demo B"
    assert alternativas[0].total_centavos == 1055000
    assert formatar_brl(alternativas[0].total_centavos) == "R$ 10.550,00"
    assert {a.oferta.id: a.motivos for a in alternativas} == {"a": ["plazo"], "b": [], "c": ["stock"]}
    respuesta = RespuestaCompra(estado="recomendacion", mensaje="Demo B", dataset_id="ref",
        solicitud=solicitud, producto_id="PROD-003", proveedor_id="B", total_centavos=1055000,
        alternativas=alternativas, evidencias=[Evidencia(tipo="catalogo", fuente_id="b",
                                                        dataset_id="ref", texto="Oferta b")])
    assert not verificar(respuesta).aprobado  # Fixture no equivale a un catálogo activo.
    assert not verificar(respuesta.model_copy(update={"total_centavos": 1054000})).aprobado


def test_escenarios_sqlite_e_identidades(tmp_path: Path):
    a = crear_catalogo(tmp_path, cantidad=20)
    b = crear_catalogo(tmp_path, cantidad=20)
    assert a.dataset_id != b.dataset_id
    assert [x.model_dump(exclude={"dataset_id"}) for x in ofertas_producto(a, "PROD-0003")] == [
        x.model_dump(exclude={"dataset_id"}) for x in ofertas_producto(b, "PROD-0003")]
    assert len(buscar_productos(a, listar_productos(a)[0].modelo)) == 1
    ruta = tmp_path / "memoria.sqlite3"
    assert nueva_sesion(ruta, "usuario-1", a.dataset_id) != nueva_sesion(ruta, "usuario-1", a.dataset_id)
    guardar_preferencia(ruta, "usuario-1", "marca", "Demo", explicita=True)
    assert preferencias(ruta, "usuario-1") == {"marca": "Demo"}
    assert preferencias(ruta, "usuario-2") == {}


def test_faltante_no_equivale_a_cero():
    assert "cantidad" in SolicitudCompra(producto="monitor").faltantes()
    assert "presupuesto_centavos" not in SolicitudCompra(producto="monitor", presupuesto_centavos=0).faltantes()
    with pytest.raises(ValueError):
        SolicitudCompra(producto="monitor", cantidad=0)
