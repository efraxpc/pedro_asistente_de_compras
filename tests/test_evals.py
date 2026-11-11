from collections import Counter

from evals.evaluar_flujo import referencias


def test_referencias_congeladas_sin_credenciales():
    casos = referencias()
    assert len(casos) == 30
    assert len({c["id"] for c in casos}) == 30
    assert Counter(c["grupo"] for c in casos) == {
        "recomendacion": 14, "sin_oferta": 5, "aclaracion": 4,
        "catalogo": 3, "cep": 2, "politica_sin_indice": 2}


def test_el_comparador_coincide_con_las_referencias_independientes(tmp_path):
    """Las referencias se calculan con SQL propio en scripts/crear_casos_eval.py."""
    import json
    import re
    from pathlib import Path

    from pedro.catalog import crear_escenario
    from pedro.contracts import Solicitud
    from pedro.verification import respuesta_local

    escenario = crear_escenario(tmp_path / "catalogos")
    casos = json.loads(Path("evals/casos_derivados.json").read_text(encoding="utf-8"))["casos"]
    comparables = [c for c in casos if c["grupo"] in ("recomendacion", "sin_oferta")]
    assert len(comparables) == 19
    for caso in comparables:
        producto_id = re.search(r"PEC-\d\d-\d{4}", caso["pregunta"]).group()
        cantidad = int(re.search(r"(\d+) unidades", caso["pregunta"]).group(1))
        respuesta = respuesta_local(escenario, Solicitud(
            producto_id=producto_id, cantidad=cantidad, presupuesto_centavos=10_000_000,
            plazo_max_dias=60))
        esperado = caso["esperado"]
        assert (respuesta.estado, respuesta.proveedor_id, respuesta.total_centavos) == (
            esperado["estado"], esperado.get("ganador"), esperado.get("total_centavos")), caso["id"]
