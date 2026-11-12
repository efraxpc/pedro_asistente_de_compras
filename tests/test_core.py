import json
import sqlite3

import pytest
from pydantic import ValidationError

from pedro.business import comparar
from pedro.catalog import abrir_cenario, criar_cenario, ofertas
from pedro.contracts import Oferta, RespostaCompra, Solicitacao
from pedro.verification import resposta_local, verificar


@pytest.fixture
def cenario(tmp_path):
    return criar_cenario(tmp_path)


def test_fonte_semente_e_cenario(cenario, tmp_path):
    meta = json.loads((cenario.caminho.parent / "manifest.json").read_text())
    assert meta["semente"] == 20261107
    assert meta["contagens"] == {"parts": 4320, "offers": 12960,
                                 "compatibility": 12960, "price_history": 77760}
    assert abrir_cenario(tmp_path, cenario.dataset_id) == cenario
    with sqlite3.connect(cenario.caminho) as db:
        assert db.execute("SELECT count(*) FROM offers WHERE part_id='PEC-01-0001'").fetchone()[0] == 3


def test_limites_empate_e_frete_unico():
    base = dict(dataset_id="d", produto_id="p", fornecedor_nome="x",
                preco_unitario_centavos=100, frete_centavos=20, estoque=2, prazo_dias=7)
    a = Oferta(id="a", fornecedor_id="B", **base)
    b = Oferta(id="b", fornecedor_id="A", **base)
    solicitacao = Solicitacao(produto_id="p", quantidade=2, orcamento_centavos=220, prazo_max_dias=7)
    alternativas = comparar(solicitacao, [a, b])
    assert [x.oferta.id for x in alternativas] == ["b", "a"]
    assert all(x.atende and x.total_centavos == 220 for x in alternativas)
    assert comparar(solicitacao.model_copy(update={"orcamento_centavos": 219}), [a])[0].motivos == ["orcamento"]
    assert comparar(solicitacao.model_copy(update={"quantidade": 3}), [a])[0].motivos == ["estoque", "orcamento"]
    assert comparar(solicitacao.model_copy(update={"prazo_max_dias": 6}), [a])[0].motivos == ["prazo"]


def test_faltante_nao_e_zero_e_json_invalido():
    assert Solicitacao(produto_id="p").faltantes() == ["quantidade"]
    with pytest.raises(ValidationError):
        Solicitacao.model_validate_json('{"produto_id":"p","quantidade":0}')
    with pytest.raises(ValidationError):
        RespostaCompra.model_validate_json("não é json")


def test_comparar_sem_limites_opcionais():
    oferta = Oferta(dataset_id="d", id="a", produto_id="p", fornecedor_id="A",
                    fornecedor_nome="x", preco_unitario_centavos=100,
                    frete_centavos=20, estoque=2, prazo_dias=30)
    alternativa = comparar(Solicitacao(produto_id="p", quantidade=2), [oferta])[0]
    assert alternativa.atende and alternativa.total_centavos == 220


def test_verificador_rejeita_omissoes_e_dataset(cenario):
    solicitacao = Solicitacao(produto_id="PEC-01-0001", quantidade=2,
                              orcamento_centavos=10_000_000, prazo_max_dias=60)
    resposta = resposta_local(cenario, solicitacao)
    assert verificar(resposta, cenario) == []
    assert len(resposta.alternativas) == len(ofertas(cenario, solicitacao.produto_id))
    assert "ofertas incompletas" in verificar(resposta.model_copy(update={
        "alternativas": resposta.alternativas[:-1]}), cenario)
    assert "evidência incompleta" in verificar(resposta.model_copy(update={
        "evidencias": resposta.evidencias[:-1]}), cenario)
    assert verificar(resposta.model_copy(update={"dataset_id": "alheio"}), cenario) == ["dataset alheio"]
    assert "vencedor ou total incorreto" in verificar(resposta.model_copy(update={
        "total_centavos": resposta.total_centavos + 1}), cenario)


def test_a_comparacao_e_ancorada_ao_calculo_da_ferramenta(tmp_path):
    from pedro.catalog import criar_cenario
    from pedro.contracts import Solicitacao
    from pedro.verification import ancorar_recomendacao, resposta_local, verificar

    cenario = criar_cenario(tmp_path / "catalogos")
    solicitacao = Solicitacao(produto_id="PEC-01-0001", quantidade=5)
    calculada = resposta_local(cenario, solicitacao)
    observacao = ("comparar_ofertas", calculada.model_dump(mode="json"))

    # O modelo copia errado o vencedor e o total.
    proposta = calculada.model_copy(deep=True)
    proposta.fornecedor_id, proposta.total_centavos = "INT-06", 1
    assert "vencedor ou total incorreto" in verificar(proposta, cenario)
    relatorio = ancorar_recomendacao(proposta, [observacao])
    assert relatorio == {"estado": "ancorada", "campos_corrigidos": ["fornecedor_id", "total_centavos"]}
    assert verificar(proposta, cenario) == []
    assert (proposta.fornecedor_id, proposta.total_centavos) == (
        calculada.fornecedor_id, calculada.total_centavos)

    # Sem um cálculo para essa mesma solicitação nada é corrigido e a verificação a rejeita.
    outra = calculada.model_copy(deep=True)
    outra.solicitacao.quantidade, outra.fornecedor_id = 6, "INT-06"
    assert ancorar_recomendacao(outra, [observacao]) == {"estado": "sem_calculo_para_essa_solicitacao"}
    assert verificar(outra, cenario) != []
    assert ancorar_recomendacao(proposta, []) == {"estado": "sem_calculo_para_essa_solicitacao"}


def test_o_pedido_minimo_descarta_uma_oferta_mesmo_sendo_a_mais_barata(tmp_path):
    from pedro.agent import renderizar
    from pedro.catalog import criar_cenario, ofertas
    from pedro.contracts import Solicitacao
    from pedro.verification import resposta_local, verificar

    cenario = criar_cenario(tmp_path / "catalogos")
    por_fornecedor = {o.fornecedor_id: o for o in ofertas(cenario, "PEC-01-0001")}
    assert (por_fornecedor["BR-06"].pedido_minimo, por_fornecedor["INT-06"].pedido_minimo) == (5, 1)
    assert por_fornecedor["BR-06"].nacional and not por_fornecedor["INT-06"].nacional

    duas = resposta_local(cenario, Solicitacao(produto_id="PEC-01-0001", quantidade=2))
    assert duas.fornecedor_id == "INT-06" and verificar(duas, cenario) == []
    centro = next(a for a in duas.alternativas if a.oferta.fornecedor_id == "BR-06")
    assert not centro.atende and centro.motivos == ["pedido_minimo"]
    assert "CentroPeças (nacional)" in renderizar(duas)
    assert "descartada por pedido mínimo (5 unidades)" in renderizar(duas)

    cinco = resposta_local(cenario, Solicitacao(produto_id="PEC-01-0001", quantidade=5))
    assert cinco.fornecedor_id == "BR-06" and cinco.total_centavos == 5 * 143892 + 8523


def test_a_preferencia_de_origem_ordena_as_ofertas_validas_e_e_explicada(tmp_path):
    from pedro.agent import renderizar
    from pedro.business import origem_preferida
    from pedro.catalog import criar_cenario
    from pedro.contracts import Solicitacao
    from pedro.verification import resposta_local, verificar

    assert origem_preferida({"fornecedor": "nacionais"}) == "nacional"
    assert origem_preferida({"fornecedores": "prefiro internacionais"}) == "internacional"
    assert origem_preferida({"cor": "azul"}) is None and origem_preferida({}) is None

    cenario = criar_cenario(tmp_path / "catalogos")
    base = Solicitacao(produto_id="PEC-01-0001", quantidade=5)
    sem_preferencia = resposta_local(cenario, base)
    internacional = resposta_local(cenario, base.model_copy(update={"origem_preferida": "internacional"}))
    # Sem preferência vence a mais barata; com ela, a da origem preferida mesmo custando mais.
    assert sem_preferencia.fornecedor_id == "BR-06" and internacional.fornecedor_id == "INT-06"
    assert internacional.total_centavos > sem_preferencia.total_centavos
    assert verificar(internacional, cenario) == []
    texto = renderizar(internacional)
    assert "Foi aplicada a sua preferência por fornecedores internacionais." in texto
    assert "Sem ela, a mais barata seria CentroPeças" in texto
    assert "preferência" not in renderizar(sem_preferencia)
    # A preferência nunca faz vencer uma oferta que não atende.
    so_duas = resposta_local(cenario, Solicitacao(produto_id="PEC-01-0001", quantidade=2,
                                                  origem_preferida="nacional"))
    assert so_duas.fornecedor_id == "INT-06"


def test_o_historico_de_precos_e_resumido_em_centavos_e_nao_muda_o_vencedor(tmp_path):
    import sqlite3

    from pedro.agent import renderizar
    from pedro.business import descrever_preco, variacao_percentual
    from pedro.catalog import criar_cenario, ofertas
    from pedro.contracts import Solicitacao
    from pedro.verification import resposta_local, verificar

    cenario = criar_cenario(tmp_path / "catalogos")
    oferta = next(o for o in ofertas(cenario, "PEC-01-0001") if o.fornecedor_id == "BR-06")
    with sqlite3.connect(cenario.caminho) as db:
        precos = [linha[0] for linha in db.execute(
            "SELECT estimated_brl_cents FROM price_history WHERE offer_id=? ORDER BY observed_on",
            (oferta.id,))]
    assert precos[-1] == oferta.preco_unitario_centavos and len(precos) == 6
    anteriores = precos[:-1]
    assert oferta.meses_historico == 5 and oferta.preco_anterior_centavos == anteriores[-1]
    assert oferta.preco_medio_centavos == round(sum(anteriores) / 5)
    assert (oferta.preco_minimo_centavos, oferta.preco_maximo_centavos) == (min(precos), max(precos))
    assert all(isinstance(getattr(oferta, campo), int) for campo in (
        "preco_medio_centavos", "preco_anterior_centavos", "preco_minimo_centavos"))

    assert (variacao_percentual(110, 100), variacao_percentual(90, 100), variacao_percentual(100, 100)) == (10, -10, 0)
    assert descrever_preco(oferta) == (
        "CentroPeças: hoje R$ 1.438,92 por unidade; mês anterior R$ 1.189,87 (+21 %); "
        "média de 5 meses R$ 1.372,51 (+5 %).")

    resposta = resposta_local(cenario, Solicitacao(produto_id="PEC-01-0001", quantidade=5))
    texto = renderizar(resposta)
    assert verificar(resposta, cenario) == []
    assert "Histórico de preços (informativo; não muda a recomendação):" in texto
    # Só se descreve o histórico das ofertas que atendem.
    assert "- CentroPeças: hoje" in texto and "- Litoral Parts: hoje" not in texto
    # O vencedor é o de menor total hoje, mesmo que o seu preço tenha subido e o do outro tenha caído.
    assert resposta.fornecedor_id == "BR-06"


def test_uma_oferta_sem_historico_nao_mostra_tendencia():
    from pedro.business import descrever_preco
    from pedro.contracts import Oferta

    oferta = Oferta(dataset_id="d", id="o", produto_id="PEC-01-0001", fornecedor_id="BR-01",
                    fornecedor_nome="Teste", preco_unitario_centavos=100, frete_centavos=0,
                    estoque=1, prazo_dias=1)
    assert descrever_preco(oferta) is None
