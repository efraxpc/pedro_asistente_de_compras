import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from langchain_core.embeddings import Embeddings

from pedro.agent import Rastro, criar_fluxo, ferramentas, renderizar
from pedro.catalog import criar_cenario
from pedro.contracts import Evidencia, RespostaCompra, Solicitacao
from pedro.policy_demo import (PERGUNTA_T24_ORIGINAL, criar_indice_demo,
                               fragmentos_demo, impressao_corpus,
                               reescrever_consulta_entrega)
from pedro.rag import consultar
from pedro.verification import verificar
from pedro.memory import Historico, nova_sessao, salvar_rascunho


class EmbeddingsTeste(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(texto) for texto in texts]

    def embed_query(self, text: str) -> list[float]:
        texto = text.lower()
        return [float("devolucao" in texto), float("garantia" in texto),
                float("entrega" in texto)]


def _corpus_teste(pasta: Path) -> None:
    for nome, palavra in (("devolucoes", "devolucao"),
                          ("garantia", "garantia"), ("entrega", "entrega")):
        (pasta / f"{nome}.md").write_text(
            f"# DEMONSTRAÇÃO T15\n\n**Versão:** 1.1\n\ncorpus sintético\n\n## Regra\n{palavra} "
            f"{palavra} exclusiva para {nome}.\n", encoding="utf-8")


def test_corpus_extenso_e_fragmentado_com_fontes_estaveis():
    documentos = fragmentos_demo()
    assert len(documentos) >= 18
    assert len({doc.id for doc in documentos}) == len(documentos)
    assert all(len(doc.page_content) <= 700 for doc in documentos)
    for tema in ("devolucoes", "garantia", "entrega"):
        fragmentos = [doc for doc in documentos if doc.metadata["tema"] == tema]
        assert len(fragmentos) >= 6
        assert all(doc.metadata["origem"] == "ficticio_demo" for doc in fragmentos)
        assert all(doc.metadata["id"] == doc.id for doc in fragmentos)
        assert all(doc.metadata["versao"] == "1.1" for doc in fragmentos)
        por_secao = Counter(doc.metadata["secao"] for doc in fragmentos)
        assert all(quantidade >= 2 for secao, quantidade in por_secao.items()
                   if secao[0].isdigit())


def test_faiss_local_filtra_e_conserva_citacoes(tmp_path):
    _corpus_teste(tmp_path)
    indice = criar_indice_demo(tmp_path, EmbeddingsTeste())
    assert not (tmp_path / "index.pkl").exists()
    assert indice.index.ntotal == len(fragmentos_demo(tmp_path))
    impressao_anterior = impressao_corpus(tmp_path)
    with (tmp_path / "garantia.md").open("a", encoding="utf-8") as arquivo:
        arquivo.write("\nNova versão fictícia.\n")
    assert impressao_corpus(tmp_path) != impressao_anterior
    resultados = consultar(indice, "garantia", k=2, filtro={"tema": "garantia"},
                           fetch_k=indice.index.ntotal)
    assert len(resultados) == 2
    assert all(r["metadados"]["tema"] == "garantia" for r in resultados)
    assert all(indice.docstore.search(r["fonte_id"]).page_content == r["texto"]
               for r in resultados)
    assert consultar(indice, "garantia", filtro={"tema": "inexistente"},
                     fetch_k=indice.index.ntotal) == []

    cenario = criar_cenario(tmp_path / "catalogos")
    resposta = RespostaCompra(
        estado="politica", dataset_id=cenario.dataset_id, solicitacao=Solicitacao(),
        mensagem="garantia exclusiva para garantia.",
        evidencias=[Evidencia(tipo="politica", fonte_id=resultados[0]["fonte_id"],
                              texto=resultados[0]["texto"])],
    )
    assert verificar(resposta, cenario, indice=indice) == []
    assert renderizar(resposta, indice=indice).startswith("Política fictícia de demonstração.")
    ferramenta = next(f for f in ferramentas(cenario, tmp_path / "memoria.sqlite3",
                                             "ana", "consulta garantia", indice)
                      if f.name == "consultar_politicas")
    assert "ficticio_demo" in ferramenta.invoke({"pergunta": "garantia"})


def test_chat_publica_politica_ficticia_com_fonte(tmp_path, monkeypatch):
    import pedro.agent as modulo

    _corpus_teste(tmp_path)
    indice = criar_indice_demo(tmp_path, EmbeddingsTeste())
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    ferramenta = next(f for f in ferramentas(cenario, memoria, "ana",
                                             "consulta devolucao", indice)
                      if f.name == "consultar_politicas")
    observacao = ferramenta.invoke({"pergunta": "devolucao"})
    fragmento = json.loads(observacao)["fragmentos"][0]
    resposta = RespostaCompra(
        estado="politica", dataset_id=cenario.dataset_id, solicitacao=Solicitacao(),
        mensagem="A devolução do corpus é fictícia.",
        evidencias=[Evidencia(tipo="politica", fonte_id=fragmento["fonte_id"],
                              texto=fragmento["texto"])],
    )

    class Executor:
        def invoke(self, entrada, config):
            return {"output": resposta.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_politicas"), observacao)]}

    class NLI:
        def classificar(self, premissa, hipotese):
            return "entailment"

    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    fluxo = criar_fluxo(cenario, memoria, llm=object(), classificador=NLI(), indice=indice)
    saida = fluxo.invoke({"input": "O que diz a política de devolução?"},
                         config={"configurable": {"user_id": "ana", "session_id": sessao}})
    assert "Política fictícia de demonstração." in saida.content
    assert fragmento["fonte_id"] in saida.content
    assert [m.type for m in Historico(memoria, "ana", sessao).todos()] == ["human", "ai"]


def test_pergunta_natural_reescreve_recupera_e_publica_rastro(tmp_path, monkeypatch):
    import pedro.agent as modulo

    assert reescrever_consulta_entrega(PERGUNTA_T24_ORIGINAL) is not None
    assert reescrever_consulta_entrega("Posso devolver várias caixas?") is None
    indice = criar_indice_demo()
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    ferramenta = next(f for f in ferramentas(cenario, memoria, "ana",
                                             PERGUNTA_T24_ORIGINAL, indice)
                      if f.name == "consultar_politicas")
    observacao = ferramenta.invoke({"pergunta": PERGUNTA_T24_ORIGINAL})
    dado = json.loads(observacao)
    assert dado["diagnostico"]["correcao_observada"] is True
    assert dado["diagnostico"]["posicao_antes"] is None
    assert dado["diagnostico"]["posicao_depois"] == 1
    fragmento = dado["fragmentos"][0]
    resposta = RespostaCompra(
        estado="politica", dataset_id=cenario.dataset_id, solicitacao=Solicitacao(),
        mensagem="Uma entrega parcial só pode ser descrita se há um acordo simulado explícito.",
        evidencias=[Evidencia(tipo="politica", fonte_id=fragmento["fonte_id"],
                              texto=fragmento["texto"])],
    )
    assert "política sem recuperação observada" in verificar(
        resposta, cenario, indice=indice, observacoes=[])

    class Executor:
        def invoke(self, entrada, config):
            raise AssertionError("a rota estável de entrega não deve depender do LLM")

    class NLI:
        def classificar(self, premissa, hipotese):
            return "entailment"

    monkeypatch.setattr(modulo, "criar_agente", lambda *args, **kwargs: Executor())
    salvar_rascunho(memoria, "ana", sessao, {"solicitacao": {"produto_id": "PEC-01-0001"},
                                            "esperando": "quantidade"})
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=object(), classificador=NLI(),
                        indice=indice, rastro=rastro)
    saida = fluxo.invoke({"input": PERGUNTA_T24_ORIGINAL},
                         config={"configurable": {"user_id": "ana", "session_id": sessao}})
    repetida = fluxo.invoke({"input": PERGUNTA_T24_ORIGINAL},
                            config={"configurable": {"user_id": "ana", "session_id": sessao}})
    assert "Política fictícia de demonstração." in saida.content
    assert "Recuperação T24" in saida.content
    assert "fora do top-4" in saida.content
    assert "posição 1" in saida.content
    assert repetida.content == saida.content
    assert [e.get("ferramenta") for e in rastro.eventos
            if e["evento"] == "tool_start"] == ["consultar_politicas"] * 2
