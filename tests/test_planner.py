import json
from types import SimpleNamespace

import pytest
from langchain_core.runnables import RunnableLambda

from pedro.agent import Rastro, criar_fluxo
from pedro.catalog import criar_cenario
from pedro.contracts import RespostaCompra, Solicitacao
from pedro.memory import Historico, nova_sessao
from pedro.planner import (PlanoTurno, intencoes_detectadas, planejar_turno, validar_plano)
from pedro.verification import resposta_local

MISTO = "Compare 5 unidades de PEC-01-0001 com prazo de 7 dias e confirme o CEP 01001000"


def _plano(*pares):
    return PlanoTurno.model_validate({"pedidos": [{"tipo": t, "pedido": p} for t, p in pares]})


def _modelo(plano: PlanoTurno):
    return RunnableLambda(lambda _: plano.model_dump_json())


def test_so_se_planeja_se_ha_sinais_de_varias_intencoes():
    assert intencoes_detectadas(MISTO) == {"compra", "cep"}
    assert intencoes_detectadas("Compare 2 unidades de PEC-01-0001") == {"compra"}
    chamado = []
    modelo = RunnableLambda(lambda _: chamado.append(1) or "{}")
    assert planejar_turno("Compare 2 unidades de PEC-01-0001", modelo) is None
    assert chamado == []


def test_um_plano_valido_devolve_os_pedidos_em_ordem():
    plano = _plano(("compra", "Compare 5 unidades de PEC-01-0001 com prazo de 7 dias"),
                   ("cep", "Confirme o CEP 01001000"))
    pedidos = planejar_turno(MISTO, _modelo(plano))
    assert [p.tipo for p in pedidos] == ["compra", "cep"]


@pytest.mark.parametrize("plano, motivo", [
    (_plano(("compra", "Compare 9 unidades de PEC-01-0001"), ("cep", "Confirme o CEP 01001000")),
     "acrescenta dados"),
    (_plano(("compra", "Compare 5 unidades de PEC-09-0009"), ("cep", "Confirme o CEP 01001000")),
     "acrescenta dados"),
    (_plano(("compra", "Compare 5 unidades de PEC-01-0001"), ("compra", "Compare PEC-01-0001")),
     "repete"),
    (_plano(("compra", "Compare 5 unidades de PEC-01-0001"), ("politica", "Conte-me algo")),
     "não parece"),
])
def test_um_plano_que_inventa_ou_nao_se_encaixa_e_descartado(plano, motivo):
    with pytest.raises(ValueError, match=motivo):
        validar_plano(plano, MISTO)
    assert planejar_turno(MISTO, _modelo(plano)) is None


def test_um_plano_ilegivel_ou_de_um_pedido_equivale_a_nao_planejar():
    assert planejar_turno(MISTO, RunnableLambda(lambda _: "não é JSON")) is None
    assert planejar_turno(MISTO, _modelo(_plano(("compra", "Compare 5 unidades de PEC-01-0001")))) is None
    assert planejar_turno(MISTO, None) is None


def test_o_fluxo_responde_cada_pedido_com_a_sua_propria_verificacao(tmp_path, monkeypatch):
    import pedro.agent as modulo

    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    compra = resposta_local(cenario, Solicitacao(produto_id="PEC-01-0001", quantidade=5, prazo_max_dias=7))
    cep = RespostaCompra(estado="cep", dataset_id=cenario.dataset_id, solicitacao=Solicitacao(cep="01001000"))
    plano = _plano(("compra", "Compare 5 unidades de PEC-01-0001 com prazo de 7 dias"),
                   ("cep", "Confirme o CEP 01001000"))
    vistos = []

    class Executor:
        def invoke(self, entrada, config):
            vistos.append(entrada["input"].splitlines()[0])
            if "CEP" in entrada["input"]:
                return {"output": cep.model_dump_json(), "intermediate_steps": [
                    (SimpleNamespace(tool="consultar_cep"), json.dumps(
                        {"estado": "ok", "cep": "01001000", "cidade": "São Paulo", "uf": "SP",
                         "modo": "simulado"}))]}
            return {"output": compra.model_dump_json(), "intermediate_steps": []}

    class NLI:
        def classificar(self, premissa, hipotese):
            return "entailment"

    class Vetores:
        modelo, versao = "test", "1"

        def embed(self, texto):
            return [1.0]

    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    monkeypatch.setattr(modulo, "FastEmbedder", Vetores)
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=_modelo(plano), classificador=NLI(), rastro=rastro)
    saida = fluxo.invoke({"input": MISTO}, config={"configurable": {
        "user_id": "ana", "session_id": sessao}}).content
    assert vistos == ["Compare 5 unidades de PEC-01-0001 com prazo de 7 dias", "Confirme o CEP 01001000"]
    assert "Sua mensagem tinha 2 pedidos" in saida
    assert "CentroPeças: R$ 7.279,83 para 5 unidades" in saida and "São Paulo/SP" in saida
    assert [e["evento"] for e in rastro.eventos if e["evento"] in ("plano", "verificacao")] == [
        "plano", "verificacao", "verificacao"]
    mensagens = Historico(memoria, "ana", sessao).todos()
    assert [m.type for m in mensagens] == ["human", "ai"] and mensagens[0].content == MISTO
