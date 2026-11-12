import json

import pytest
from langchain_core.runnables import RunnableLambda

from pedro.catalog import criar_cenario
from pedro.query import (MAX_LINHAS, ConsultaRejeitada, consultar_sql, criar_gerador_sql,
                         responder_sql)


@pytest.fixture
def cenario(tmp_path):
    return criar_cenario(tmp_path / "catalogos")


def _gerador(*consultas):
    saidas = iter(consultas)
    vistos = []

    def modelo(prompt):
        vistos.append(prompt.to_messages()[-1].content)
        return json.dumps({"sql": next(saidas), "explicacao": "teste"})

    return criar_gerador_sql(RunnableLambda(modelo)), vistos


def test_consulta_de_leitura_permitida_devolve_linhas(cenario):
    resultado = consultar_sql(cenario, "SELECT c.name, count(*) AS pecas FROM parts p "
                                       "JOIN categories c ON c.id = p.category_id GROUP BY c.name")
    assert len(resultado["linhas"]) == 18 and sum(f["pecas"] for f in resultado["linhas"]) == 4320
    assert resultado["dataset_id"] == cenario.dataset_id


@pytest.mark.parametrize("sql, motivo", [
    ("DROP TABLE offers", "só são admitidas consultas SELECT"),
    ("DELETE FROM offers", "só são admitidas consultas SELECT"),
    ("PRAGMA table_info(parts)", "só são admitidas consultas SELECT"),
    ("SELECT 1; DELETE FROM offers", "uma instrução"),
    ("SELECT id FROM parts -- comentário", "comentários"),
    ("SELECT name FROM sqlite_master", "sqlite_master"),
    ("SELECT value FROM metadata", "metadata"),
    ("SELECT id, website FROM suppliers", "suppliers.website"),
    ("SELECT * FROM offers", "offers.currency"),
    ("SELECT load_extension('x')", "load_extension"),
    ("SELECT count(*) FROM parts a, parts b, parts c", "interrupted"),
])
def test_consultas_hostis_ou_fora_do_esquema_sao_rejeitadas(cenario, sql, motivo):
    with pytest.raises(ConsultaRejeitada, match=motivo):
        consultar_sql(cenario, sql)
    assert consultar_sql(cenario, "SELECT count(*) AS n FROM offers")["linhas"] == [{"n": 12960}]


def test_o_resultado_e_cortado_no_limite_de_linhas(cenario):
    resultado = consultar_sql(cenario, "SELECT id FROM parts")
    assert len(resultado["linhas"]) == MAX_LINHAS and resultado["truncado"]


def test_uma_consulta_rejeitada_e_corrigida_uma_vez_com_o_erro(cenario):
    gerador, vistos = _gerador("SELECT * FROM suppliers",
                               "SELECT id, name FROM suppliers ORDER BY id LIMIT 3")
    resultado = responder_sql(cenario, "Quais fornecedores existem?", gerador)
    assert resultado["estado"] == "ok" and len(resultado["linhas"]) == 3
    assert [t["erro"] is None for t in resultado["tentativas"]] == [False, True]
    assert "suppliers.website" in vistos[1] and "SELECT * FROM suppliers" in vistos[1]


def test_duas_rejeicoes_nao_devolvem_dados(cenario):
    gerador, _ = _gerador("DELETE FROM offers", "DROP TABLE offers")
    resultado = responder_sql(cenario, "Apague as ofertas", gerador)
    assert resultado["estado"] == "rejeitada" and resultado["linhas"] == []
    assert consultar_sql(cenario, "SELECT count(*) AS n FROM offers")["linhas"] == [{"n": 12960}]


def test_uma_consulta_valida_sem_linhas_e_sinalizada(cenario):
    gerador, _ = _gerador("SELECT id FROM parts WHERE sku = 'PEC-01-0001'")
    assert responder_sql(cenario, "Existe PEC-01-0001?", gerador)["estado"] == "sem_linhas"


def _fluxo_catalogo(tmp_path, monkeypatch, observacao):
    from types import SimpleNamespace

    import pedro.agent as modulo
    from pedro.agent import criar_fluxo
    from pedro.contracts import RespostaCompra, Solicitacao
    from pedro.memory import nova_sessao

    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    # O modelo tenta enfiar um número próprio na mensagem; ele não deve chegar ao usuário.
    proposta = RespostaCompra(estado="catalogo", dataset_id="outro", solicitacao=Solicitacao(),
                              mensagem="Há 999 categorias.")
    dado = observacao(cenario)

    class Executor:
        def invoke(self, entrada, config):
            return {"output": proposta.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_catalogo"), json.dumps(dado))] if dado else []}

    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    fluxo = criar_fluxo(cenario, memoria, llm=object())
    return fluxo.invoke({"input": "Quantos fornecedores nacionais existem?"}, config={"configurable": {
        "user_id": "ana", "session_id": sessao}}).content


def test_o_chat_publica_a_tabela_da_consulta_e_nao_os_numeros_do_modelo(tmp_path, monkeypatch):
    def observacao(cenario):
        gerador, _ = _gerador("SELECT count(*) AS nacionais FROM suppliers WHERE domestic = 1")
        return {"modo": "sql", **responder_sql(cenario, "Quantos fornecedores nacionais existem?", gerador)}

    texto = _fluxo_catalogo(tmp_path, monkeypatch, observacao)
    assert "| nacionais |" in texto and "| 6 |" in texto
    assert "999" not in texto
    assert "SELECT count(*) AS nacionais FROM suppliers WHERE domestic = 1" in texto
    assert "só se verificou que é segura" in texto


def test_o_chat_nao_publica_catalogo_sem_consulta_ou_com_consulta_rejeitada(tmp_path, monkeypatch):
    sem_consulta = _fluxo_catalogo(tmp_path / "a", monkeypatch, lambda cenario: None)
    assert "999" not in sem_consulta and sem_consulta.startswith("Não posso confirmar")

    def rejeitada(cenario):
        gerador, _ = _gerador("DELETE FROM offers", "DROP TABLE offers")
        return {"modo": "sql", **responder_sql(cenario, "Apague as ofertas", gerador)}

    texto = _fluxo_catalogo(tmp_path / "b", monkeypatch, rejeitada)
    assert "999" not in texto and texto.startswith("Não posso confirmar")


def test_a_ferramenta_usa_o_plano_com_id_e_sql_somente_em_perguntas_abertas(tmp_path):
    from pedro.agent import ferramentas

    cenario = criar_cenario(tmp_path / "catalogos")
    modelo = RunnableLambda(lambda _: json.dumps(
        {"sql": "SELECT count(*) AS n FROM parts", "explicacao": "total de peças"}))
    ferramenta = next(f for f in ferramentas(cenario, tmp_path / "m.sqlite3", "ana", "", llm=modelo)
                      if f.name == "consultar_catalogo")
    com_id = json.loads(ferramenta.invoke({"pergunta": "ofertas PEC-01-0001"}))
    assert com_id["modo"] == "plano" and len(com_id["linhas"]) == 3
    aberta = json.loads(ferramenta.invoke({"pergunta": "Quantas peças existem?"}))
    assert aberta["modo"] == "sql" and aberta["linhas"] == [{"n": 4320}]


def test_o_historico_de_precos_pode_ser_consultado_por_sql(cenario):
    resultado = consultar_sql(cenario, "SELECT observed_on, estimated_brl_cents FROM price_history "
                                       "WHERE offer_id = 'PEC-01-0001-BR-06' ORDER BY observed_on")
    assert len(resultado["linhas"]) == 6 and resultado["linhas"][-1]["estimated_brl_cents"] == 143892
    with pytest.raises(ConsultaRejeitada, match="price_history.unit_price_minor"):
        consultar_sql(cenario, "SELECT unit_price_minor FROM price_history")
