from collections import Counter

from evals.evaluar_flujo import referencias


def test_referencias_congeladas_sin_credenciales():
    casos = referencias()
    assert len(casos) == 30
    assert len({c["id"] for c in casos}) == 30
    assert Counter(c["grupo"] for c in casos) == {
        "recomendacion": 14, "sin_oferta": 5, "aclaracion": 4,
        "catalogo": 3, "cep": 2, "politica_sin_indice": 2}
