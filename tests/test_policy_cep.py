from types import SimpleNamespace

from langchain_core.documents import Document

from pedro.catalog import criar_cenario
from pedro.contracts import Evidencia, RespostaCompra, Solicitacao
from pedro.nli import verificar_nli
from pedro.verification import verificar
from pedro.memory import Historico, nova_sessao
from pedro.agent import criar_fluxo


def test_cep_exige_observacao_coincidente(tmp_path):
    cenario = criar_cenario(tmp_path)
    resposta = RespostaCompra(estado="cep", dataset_id=cenario.dataset_id,
        solicitacao=Solicitacao(cep="01001000"), cidade="São Paulo", uf="SP", modo_cep="real",
        evidencias=[Evidencia(tipo="viacep", fonte_id="ViaCEP:01001000", texto="São Paulo/SP")])
    observacao = ("consultar_cep", {"estado": "ok", "cep": "01001000",
                                    "cidade": "São Paulo", "uf": "SP", "modo": "real"})
    assert verificar(resposta, cenario, observacoes=[observacao]) == []
    assert "localização não coincide com o ViaCEP" in verificar(resposta, cenario)
    falso = resposta.model_copy(update={"uf": "RJ"})
    assert "localização não coincide com o ViaCEP" in verificar(falso, cenario,
                                                                observacoes=[observacao])


def test_politica_exige_fragmento_e_entailment(tmp_path):
    cenario = criar_cenario(tmp_path)
    doc = Document(page_content="A devolução fictícia é admitida dentro de 30 dias.")
    indice = SimpleNamespace(docstore=SimpleNamespace(search=lambda _id: doc))
    resposta = RespostaCompra(estado="politica", dataset_id=cenario.dataset_id,
        solicitacao=Solicitacao(), mensagem="A devolução fictícia é admitida dentro de 30 dias.",
        evidencias=[Evidencia(tipo="politica", fonte_id="politica-1", texto=doc.page_content)])
    assert verificar(resposta, cenario, indice=indice) == []
    assert verificar(resposta, cenario) == ["política sem índice ou afirmação"]
    alterada = resposta.model_copy(update={"evidencias": [Evidencia(
        tipo="politica", fonte_id="politica-1", texto="texto inventado")]})
    assert verificar(alterada, cenario, indice=indice)

    class Rotulo:
        def __init__(self, rotulo):
            self.rotulo = rotulo
        def classificar(self, premissa, hipotese):
            return self.rotulo

    assert verificar_nli(resposta, Rotulo("entailment"))
    assert not verificar_nli(resposta, Rotulo("neutral"))
    assert not verificar_nli(resposta, Rotulo("contradiction"))


def test_fluxo_publica_cep_somente_apos_observacao(tmp_path, monkeypatch):
    import pedro.agent as modulo
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    resposta = RespostaCompra(estado="cep", dataset_id=cenario.dataset_id,
        solicitacao=Solicitacao(cep="01001000"), cidade="São Paulo", uf="SP", modo_cep="real",
        evidencias=[Evidencia(tipo="viacep", fonte_id="ViaCEP:01001000", texto="São Paulo/SP")])
    class Executor:
        def invoke(self, entrada, config):
            return {"output": resposta.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_cep"),
                 '{"estado":"ok","cep":"01001000","cidade":"São Paulo","uf":"SP","modo":"real"}')]
            }
    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    fluxo = criar_fluxo(cenario, memoria, llm=object())
    saida = fluxo.invoke({"input": "Consulte o CEP 01001000"}, config={"configurable": {
        "user_id": "ana", "session_id": sessao}})
    assert "São Paulo/SP" in saida.content
    assert len(Historico(memoria, "ana", sessao).todos()) == 2


def test_cep_e_ancorado_na_observacao_e_sem_ela_e_rejeitado(tmp_path):
    from pedro.verification import ancorar_cep

    cenario = criar_cenario(tmp_path / "catalogos")
    observacao = ("consultar_cep", {"estado": "ok", "cep": "01001000", "cidade": "São Paulo",
                                    "uf": "SP", "modo": "real"})
    # O modelo erra no mecânico: outro dataset, sem evidência e com a cidade mal escrita.
    resposta = RespostaCompra(estado="cep", dataset_id="outro", solicitacao=Solicitacao(cep="01001000"),
                              cidade="Sao Paulo", uf="SP")
    assert verificar(resposta, cenario, observacoes=[observacao]) == ["dataset alheio"]
    assert ancorar_cep(resposta, [observacao], cenario.dataset_id)["estado"] == "ancorada"
    assert verificar(resposta, cenario, observacoes=[observacao]) == []
    assert (resposta.cidade, resposta.modo_cep) == ("São Paulo", "real")
    assert resposta.evidencias[0].fonte_id == "ViaCEP:01001000"

    inventada = RespostaCompra(estado="cep", dataset_id="outro", solicitacao=Solicitacao(cep="99999999"),
                               cidade="Cidade Inventada", uf="XX", modo_cep="real")
    sem_dado = ("consultar_cep", {"estado": "nao_encontrado", "cep": "99999999"})
    assert ancorar_cep(inventada, [sem_dado], cenario.dataset_id)["estado"] == "sem_observacao_valida"
    assert verificar(inventada, cenario, observacoes=[sem_dado]) == ["dataset alheio"]
    outro_cep = RespostaCompra(estado="cep", dataset_id=cenario.dataset_id,
                               solicitacao=Solicitacao(cep="20040020"), cidade="Rio", uf="RJ", modo_cep="real")
    assert ancorar_cep(outro_cep, [observacao], cenario.dataset_id)["estado"] == "sem_observacao_valida"
    assert verificar(outro_cep, cenario, observacoes=[observacao]) != []


def test_fluxo_explica_um_cep_inexistente_sem_inventar_cidade(tmp_path, monkeypatch):
    import pedro.agent as modulo
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    inventada = RespostaCompra(estado="cep", dataset_id=cenario.dataset_id,
                               solicitacao=Solicitacao(cep="99999999"), cidade="Cidade Inventada",
                               uf="XX", modo_cep="real")

    class Executor:
        def invoke(self, entrada, config):
            return {"output": inventada.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_cep"), '{"estado":"nao_encontrado","cep":"99999999"}')]}

    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    fluxo = criar_fluxo(cenario, memoria, llm=object())
    saida = fluxo.invoke({"input": "Consulte o CEP 99999999"}, config={"configurable": {
        "user_id": "ana", "session_id": sessao}})
    assert saida.content == "O ViaCEP não tem registro do CEP 99999999."
    assert "Inventada" not in saida.content
