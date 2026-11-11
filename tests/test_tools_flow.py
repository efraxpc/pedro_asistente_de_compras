from pedro.agent import Rastro, criar_fluxo, ferramentas
from pedro.catalog import criar_cenario
from pedro.memory import Historico, nova_sessao
from pedro.query import executar, planejar


def test_sql_plano_e_ferramentas(tmp_path):
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    nova_sessao(memoria, "ana", cenario.dataset_id)
    resultado = executar(cenario, "ofertas PEC-01-0001", planejar("ofertas PEC-01-0001"))
    assert len(resultado["linhas"]) == 3
    assert resultado["parametros"] == ["PEC-01-0001", 20]
    assert "?" in resultado["sql"]
    assert len(ferramentas(cenario, memoria, "ana", "olá")) == 6


def test_rastro_oculta_chaves_e_registra_fontes():
    rastro = Rastro()
    rastro.on_tool_start({"name": "consultar_catalogo"}, "sk-abcdefghijklmnop")
    rastro.on_tool_end('{"evidencias":[{"fonte_id":"oferta-1"}]}')
    assert "sk-" not in rastro.eventos[0]["entrada"]
    assert rastro.eventos[0]["rota"] == "consultar_catalogo"
    assert rastro.eventos[1]["fontes"] == ["oferta-1"]


def test_fluxo_local_persiste_so_o_publico(tmp_path):
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    fluxo = criar_fluxo(cenario, memoria)
    saida = fluxo.invoke({"input": "lista peças"}, config={"configurable": {
        "user_id": "ana", "session_id": sessao}})
    assert "PEC-01-0001" in saida.content
    mensagens = Historico(memoria, "ana", sessao).todos()
    assert [m.type for m in mensagens] == ["human", "ai"]
    assert len(mensagens[1].content.splitlines()) == 21


def test_correcao_interna_e_publicacao_final(tmp_path, monkeypatch):
    import pedro.agent as modulo
    from pedro.contracts import Solicitacao
    from pedro.verification import resposta_local

    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    proposta = resposta_local(cenario, Solicitacao(produto_id="PEC-01-0001", quantidade=1,
        orcamento_centavos=10_000_000, prazo_max_dias=60))
    chamadas = []

    class Executor:
        def invoke(self, entrada, config):
            chamadas.append(entrada)
            return {"output": "json inválido" if len(chamadas) == 1 else proposta.model_dump_json()}

    class NLI:
        def classificar(self, premissa, hipotese):
            return "entailment"

    class Vetores:
        modelo, versao = "test", "1"
        def embed(self, texto):
            return [1.0]

    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    monkeypatch.setattr(modulo, "FastEmbedder", Vetores)
    fluxo = criar_fluxo(cenario, memoria, llm=object(), classificador=NLI())
    saida = fluxo.invoke({"input": "recomende 1 unidade de PEC-01-0001; orçamento R$ 100000 e prazo 60 dias"}, config={"configurable": {
        "user_id": "ana", "session_id": sessao}})
    assert len(chamadas) == 2
    assert proposta.fornecedor_id in saida.content or proposta.alternativas[0].oferta.fornecedor_nome in saida.content
    assert [m.type for m in Historico(memoria, "ana", sessao).todos()] == ["human", "ai"]


def test_modelo_nao_publica_quantidade_antiga(tmp_path, monkeypatch):
    import pedro.agent as modulo
    from pedro.contracts import Solicitacao
    from pedro.verification import resposta_local

    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    proposta_antiga = resposta_local(cenario, Solicitacao(
        produto_id="PEC-01-0001", quantidade=2))
    chamadas = []

    class Executor:
        def invoke(self, entrada, config):
            chamadas.append(entrada)
            return {"output": proposta_antiga.model_dump_json()}

    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    fluxo = criar_fluxo(cenario, memoria, llm=object())
    saida = fluxo.invoke({"input": "Compare 3 unidades de PEC-01-0001"},
                         config={"configurable": {"user_id": "ana", "session_id": sessao}})
    assert len(chamadas) == 2
    assert "Não posso confirmar" in saida.content


def test_rastro_registra_cada_verificacao_com_os_seus_erros(tmp_path, monkeypatch):
    import pedro.agent as modulo
    from pedro.contracts import Solicitacao
    from pedro.verification import resposta_local

    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    proposta = resposta_local(cenario, Solicitacao(produto_id="PEC-01-0001", quantidade=1))
    saidas = iter(["json inválido", proposta.model_dump_json()])

    class Executor:
        def invoke(self, entrada, config):
            return {"output": next(saidas)}

    class NLI:
        def classificar(self, premissa, hipotese):
            return "entailment"

    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=object(), classificador=NLI(), rastro=rastro)
    fluxo.invoke({"input": "Compare 1 unidade de PEC-01-0001"}, config={"configurable": {
        "user_id": "ana", "session_id": sessao}})
    verificacoes = [e for e in rastro.eventos if e["evento"] == "verificacao"]
    assert [(v["tentativa"], v["estado"], v["erros"]) for v in verificacoes] == [
        (1, None, ["OutputParserException"]), (2, "recomendacao", [])]


def test_a_resposta_anexa_a_comparacao_estruturada_e_ela_se_conserva_no_historico(tmp_path):
    from pedro.agent import partes_de
    from pedro.contracts import RespostaCompra

    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    fluxo = criar_fluxo(cenario, memoria)
    config = {"configurable": {"user_id": "ana", "session_id": sessao}}
    saida = fluxo.invoke({"input": "Compare 5 unidades de PEC-01-0001"}, config=config)
    (parte,) = partes_de(saida)
    comparacao = RespostaCompra.model_validate(parte["comparacao"])
    assert comparacao.fornecedor_id == "BR-06" and parte["texto"] == saida.content
    # Depois de reler o histórico, a interface pode desenhar de novo a mesma comparação.
    salvo = Historico(memoria, "ana", sessao).todos()[-1]
    assert partes_de(salvo) == [parte]
    # Uma resposta que não é uma comparação leva só texto.
    listagem = fluxo.invoke({"input": "lista peças"}, config=config)
    assert partes_de(listagem) == [{"titulo": None, "texto": listagem.content, "comparacao": None,
                                    "conselho": None}]
