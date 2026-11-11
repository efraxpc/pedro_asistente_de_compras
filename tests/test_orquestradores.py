"""O mesmo agente em dois orquestradores, com um modelo duplo que pede uma ferramenta."""
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from pedro.catalog import criar_cenario
from pedro.orquestradores import agente_langchain, agente_langgraph, ferramentas_basicas


class ModeloDuplo(FakeMessagesListChatModel):
    """Devolve mensagens roteirizadas; aceitar `bind_tools` basta para montar um agente."""

    def bind_tools(self, tools, **kwargs):
        return self


def _roteiro():
    return ModeloDuplo(responses=[
        AIMessage(content="", tool_calls=[{"name": "buscar_peca", "args": {"texto": "GELA-COMP-0001"},
                                           "id": "c1"}]),
        AIMessage(content="O ID é PEC-01-0001."),
        AIMessage(content="Falávamos de PEC-01-0001."),
        AIMessage(content="Não falamos de nenhuma peça.")])


def test_as_ferramentas_basicas_leem_o_catalogo(tmp_path):
    buscar, ofertas = ferramentas_basicas(criar_cenario(tmp_path / "catalogos"))
    assert "PEC-01-0001" in buscar.invoke({"texto": "GELA-COMP-0001"})
    assert "CentroPeças" in ofertas.invoke({"produto_id": "PEC-01-0001"})


@pytest.mark.parametrize("construtor", [agente_langchain, agente_langgraph])
def test_os_dois_orquestradores_executam_a_ferramenta_e_separam_os_fios(tmp_path, construtor):
    if construtor is agente_langgraph:
        pytest.importorskip("langgraph")
    conversar = construtor(_roteiro(), criar_cenario(tmp_path / "catalogos"))
    primeiro = conversar("Busque GELA-COMP-0001", "fio-a")
    assert primeiro["resposta"] == "O ID é PEC-01-0001."
    assert primeiro["ferramentas"] == ["buscar_peca({'texto': 'GELA-COMP-0001'})"]
    assert conversar("Do que falávamos?", "fio-a")["ferramentas"] == []
    assert conversar("Do que falávamos?", "fio-b")["resposta"] == "Não falamos de nenhuma peça."


def test_langmem_salva_por_usuario_o_que_o_modelo_decide_lembrar(tmp_path):
    pytest.importorskip("langmem")
    from langchain_core.embeddings import Embeddings

    from pedro.orquestradores import agente_com_langmem

    class Vetores(Embeddings):
        def embed_documents(self, texts):
            return [[1.0, 0.0, 0.0] for _ in texts]

        def embed_query(self, text):
            return [1.0, 0.0, 0.0]

    modelo = ModeloDuplo(responses=[
        AIMessage(content="", tool_calls=[{"name": "manage_memory", "id": "m1", "args": {
            "content": "Prefere fornecedores nacionais.", "action": "create"}}]),
        AIMessage(content="Vou lembrar.")])
    conversar, armazem = agente_com_langmem(modelo, criar_cenario(tmp_path / "catalogos"),
                                            Vetores(), 3)
    turno = conversar("Prefiro fornecedores nacionais, lembre-se disso", "ana", "fio-1")
    assert turno["resposta"] == "Vou lembrar." and turno["ferramentas"][0].startswith("manage_memory")
    assert [item.value["content"] for item in armazem.search(("lembrancas", "ana"))] == [
        "Prefere fornecedores nacionais."]
    assert armazem.search(("lembrancas", "luis")) == []
