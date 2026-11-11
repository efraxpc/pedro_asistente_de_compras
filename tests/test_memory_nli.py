import pytest
from langchain_core.messages import AIMessage, HumanMessage

from pedro.catalog import criar_cenario
from pedro.contracts import Solicitacao
from pedro.memory import (Historico, atualizar_episodio, nova_sessao, preferencias, recuperar,
                          salvar_episodio, salvar_preferencia)
from pedro.nli import verificar_nli
from pedro.verification import resposta_local


class Vetores:
    modelo = "test"
    versao = "1"

    def embed(self, texto):
        return [float("azul" in texto), float("vermelho" in texto)]


def test_memoria_isolada_e_atualizada(tmp_path):
    caminho = tmp_path / "memoria.sqlite3"
    a = nova_sessao(caminho, "ana", "dataset-a")
    nova_sessao(caminho, "beto", "dataset-b")
    ha = Historico(caminho, "ana", a)
    ha.add_messages([HumanMessage(content="quero dois"), AIMessage(content="entendido")])
    assert len(ha.todos()) == 2
    with pytest.raises(ValueError):
        Historico(caminho, "beto", a)
    for i in range(14):
        ha.add_messages([HumanMessage(content=f"turno {i}")])
    assert len(ha.messages) == 12
    assert len(ha.todos()) == 16
    salvar_preferencia(caminho, "ana", "cor", "azul", explicita=True)
    assert preferencias(caminho, "beto") == {}
    episodio = salvar_episodio(caminho, "ana", a, "azul", Vetores())
    assert recuperar(caminho, "ana", "azul", Vetores())[0]["id"] == episodio
    assert recuperar(caminho, "beto", "azul", Vetores()) == []
    atualizar_episodio(caminho, "ana", episodio, "vermelho", Vetores())
    assert recuperar(caminho, "ana", "vermelho", Vetores())[0]["texto"] == "vermelho"


@pytest.mark.parametrize("rotulo,esperado", [("entailment", True),
                                             ("contradiction", False), ("neutral", False)])
def test_nli_triclasse(tmp_path, rotulo, esperado):
    cenario = criar_cenario(tmp_path)
    resposta = resposta_local(cenario, Solicitacao(produto_id="PEC-01-0001", quantidade=1,
        orcamento_centavos=10_000_000, prazo_max_dias=60))

    class Classificador:
        def classificar(self, premissa, hipotese):
            assert resposta.fornecedor_id in hipotese or "estoque" in hipotese
            return rotulo

    assert verificar_nli(resposta, Classificador()) is esperado


def test_mapa_de_memorias_reflete_o_que_foi_salvo_por_usuario_e_sessao(tmp_path):
    from pedro.memory import mapa_memorias, salvar_rascunho

    caminho = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(caminho, "ana", "demo")
    salvar_rascunho(caminho, "ana", sessao, {"solicitacao": {"produto_id": "PEC-01-0001", "quantidade": 3,
                                                             "prazo_max_dias": None}})
    salvar_preferencia(caminho, "ana", "fornecedor", "nacionais", explicita=True)
    mapa = mapa_memorias(caminho, "ana", sessao)
    assert mapa["trabalho (curto prazo, por sessão)"]["rascunho_de_compra"] == {
        "produto_id": "PEC-01-0001", "quantidade": 3}
    assert mapa["semântica (longo prazo)"]["preferencias_do_usuario"] == {"fornecedor": "nacionais"}
    assert mapa["episódica (longo prazo, por usuário)"]["episodios"] == 0
    outra = nova_sessao(caminho, "luis", "demo")
    alheio = mapa_memorias(caminho, "luis", outra)
    assert alheio["trabalho (curto prazo, por sessão)"]["rascunho_de_compra"] == {}
    assert alheio["semântica (longo prazo)"]["preferencias_do_usuario"] == {}
