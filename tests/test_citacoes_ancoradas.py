import json
from types import SimpleNamespace

import pytest

from pedro.agent import Rastro, criar_fluxo
from pedro.catalog import criar_cenario
from pedro.contracts import Evidencia, RespostaCompra, Solicitacao
from pedro.memory import nova_sessao
from pedro.policy_demo import criar_indice_demo
from pedro.verification import ancorar_citacao, ancorar_citacoes
from tests.test_policy_demo import EmbeddingsTeste

FRAGMENTO = ("O dano visível ao abrir a caixa deve ser notificado dentro de **7 dias corridos** "
             "desde a entrega simulada. A notificação deve incluir uma fotografia da caixa.")
CITACAO_QUASE_LITERAL = ("O dano visível ao abrir a caixa deve ser notificado dentro de 7 dias corridos "
                         "desde a entrega simulada...")


def test_citacao_quase_literal_e_ancorada_no_texto_do_fragmento():
    trecho, cobertura = ancorar_citacao(CITACAO_QUASE_LITERAL, FRAGMENTO)
    assert trecho is not None and trecho in FRAGMENTO
    assert "**7 dias corridos**" in trecho and cobertura >= 0.8


@pytest.mark.parametrize("citacao", [
    "O dano visível pode ser notificado a qualquer momento e sem fotografias da caixa.",
    "A garantia cobre doze meses de uso doméstico contínuo do compressor.",
    "7 dias",
])
def test_citacao_inventada_ou_curta_demais_nao_e_ancorada(citacao):
    assert ancorar_citacao(citacao, FRAGMENTO)[0] is None


def test_ancorar_citacoes_informa_o_estado_de_cada_fonte():
    observacoes = [("consultar_politicas", {"fragmentos": [
        {"fonte_id": "A", "texto": FRAGMENTO}, {"fonte_id": "B", "texto": FRAGMENTO}]})]
    resposta = RespostaCompra(estado="politica", dataset_id="d", solicitacao=Solicitacao(), evidencias=[
        Evidencia(tipo="politica", fonte_id="A", texto=CITACAO_QUASE_LITERAL),
        Evidencia(tipo="politica", fonte_id="B", texto=""),
        Evidencia(tipo="politica", fonte_id="A", texto="Texto que a fonte não contém de forma alguma."),
        Evidencia(tipo="politica", fonte_id="Z", texto=FRAGMENTO)])
    estados = [c["estado"] for c in ancorar_citacoes(resposta, observacoes)]
    assert estados == ["reancorada", "por_identificador", "rejeitada", "fonte_nao_recuperada"]
    assert resposta.evidencias[0].texto in FRAGMENTO
    assert resposta.evidencias[1].texto == FRAGMENTO


def _chat(tmp_path, monkeypatch, citacao, rotulo_nli):
    import pedro.agent as modulo

    (tmp_path / "devolucoes.md").write_text(
        "# DEMONSTRAÇÃO\n\n**Versão:** 1.1\n\ncorpus sintético\n\n## Regra\n" + FRAGMENTO + "\n",
        encoding="utf-8")
    for nome in ("garantia", "entrega"):
        (tmp_path / f"{nome}.md").write_text(
            f"# DEMONSTRAÇÃO\n\n**Versão:** 1.1\n\ncorpus sintético\n\n## Regra\n{nome} {nome}.\n",
            encoding="utf-8")
    indice = criar_indice_demo(tmp_path, EmbeddingsTeste())
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    fonte_id = next(i for i, d in indice.docstore._dict.items() if FRAGMENTO[:40] in d.page_content)
    literal = indice.docstore.search(fonte_id).page_content
    observacao = json.dumps({"fragmentos": [{"fonte_id": fonte_id, "texto": literal}]})
    # O modelo copia mal o identificador do cenário; isso não deve impedir a publicação.
    resposta = RespostaCompra(
        estado="politica", dataset_id="identificador-mal-copiado", solicitacao=Solicitacao(),
        mensagem="O dano visível é notificado em 7 dias corridos.",
        evidencias=[Evidencia(tipo="politica", fonte_id=fonte_id, texto=citacao)])

    class Executor:
        def invoke(self, entrada, config):
            return {"output": resposta.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_politicas"), observacao)]}

    class NLI:
        def classificar(self, premissa, hipotese):
            return rotulo_nli

    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=object(), classificador=NLI(), indice=indice,
                        rastro=rastro)
    saida = fluxo.invoke({"input": "O que diz a política de devolução sobre danos?"},
                         config={"configurable": {"user_id": "ana", "session_id": sessao}})
    estados = [c["estado"] for e in rastro.eventos if e["evento"] == "citacoes_ancoradas"
               for c in e["citacoes"]]
    return saida.content, estados, fonte_id


def test_chat_publica_resumo_quando_a_citacao_e_reancorada_e_ha_entailment(tmp_path, monkeypatch):
    texto, estados, fonte_id = _chat(tmp_path, monkeypatch, CITACAO_QUASE_LITERAL, "entailment")
    assert "O dano visível é notificado em 7 dias corridos." in texto and fonte_id in texto
    assert estados == ["reancorada"]


def test_chat_degrada_para_citacao_textual_se_o_resumo_nao_tem_entailment(tmp_path, monkeypatch):
    texto, estados, fonte_id = _chat(tmp_path, monkeypatch, CITACAO_QUASE_LITERAL, "neutral")
    assert "cito o texto literal" in texto and "**7 dias corridos**" in texto
    assert "O dano visível é notificado em 7 dias corridos." not in texto
    assert fonte_id in texto and estados == ["reancorada", "reancorada"]


def test_chat_nao_publica_uma_citacao_inventada(tmp_path, monkeypatch):
    texto, estados, _ = _chat(tmp_path, monkeypatch,
                              "O dano visível pode ser notificado sem prazo e sem fotografias.",
                              "entailment")
    assert texto.startswith("Não consegui verificar a resposta sobre políticas")
    assert estados == ["rejeitada", "rejeitada"]
