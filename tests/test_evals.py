from collections import Counter

from evals.avaliar_fluxo import referencias


def test_referencias_congeladas_sem_credenciais():
    casos = referencias()
    assert len(casos) == 30
    assert len({c["id"] for c in casos}) == 30
    assert Counter(c["grupo"] for c in casos) == {
        "recomendacao": 14, "sem_oferta": 5, "esclarecimento": 4,
        "catalogo": 3, "cep": 2, "politica_sem_indice": 2}


def test_o_comparador_coincide_com_as_referencias_independentes(tmp_path):
    """As referências são calculadas com SQL próprio em scripts/criar_casos_eval.py."""
    import json
    import re
    from pathlib import Path

    from pedro.catalog import criar_cenario
    from pedro.contracts import Solicitacao
    from pedro.verification import resposta_local

    cenario = criar_cenario(tmp_path / "catalogos")
    casos = json.loads(Path("evals/casos_derivados.json").read_text(encoding="utf-8"))["casos"]
    comparaveis = [c for c in casos if c["grupo"] in ("recomendacao", "sem_oferta")]
    assert len(comparaveis) == 19
    for caso in comparaveis:
        produto_id = re.search(r"PEC-\d\d-\d{4}", caso["pergunta"]).group()
        quantidade = int(re.search(r"(\d+) unidades", caso["pergunta"]).group(1))
        resposta = resposta_local(cenario, Solicitacao(
            produto_id=produto_id, quantidade=quantidade, orcamento_centavos=10_000_000,
            prazo_max_dias=60))
        esperado = caso["esperado"]
        assert (resposta.estado, resposta.fornecedor_id, resposta.total_centavos) == (
            esperado["estado"], esperado.get("vencedor"), esperado.get("total_centavos")), caso["id"]
