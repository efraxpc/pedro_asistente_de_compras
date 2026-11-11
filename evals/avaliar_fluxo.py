"""Avaliação remota do mesmo fluxo final usado pelo Streamlit."""
import argparse
import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client, evaluate

from pedro.agent import Rastro, criar_fluxo
from pedro.catalog import SOURCE, criar_cenario
from pedro.memory import nova_sessao
from pedro.nli import MODELO, REVISAO, ModeloNLI

CASOS_CAMINHO = Path("evals/casos_derivados.json")


def referencias() -> list[dict]:
    dado = json.loads(CASOS_CAMINHO.read_text(encoding="utf-8"))
    if dado["tipo"] != "derivados_sinteticos_nao_oficiais" or len(dado["casos"]) != 30:
        raise ValueError("são necessários 30 casos derivados congelados")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != dado["fonte_sha256"]:
        raise ValueError("as referências pertencem a outra versão do catálogo")
    return dado["casos"]


def _saida(run) -> dict:
    return run.outputs or {}


def avaliar_conteudo(run, example):
    esperado = example.outputs or {}
    texto = str(_saida(run).get("resposta", ""))
    return {"key": "conteudo", "score": int(esperado["contem"] in texto)
            if "contem" in esperado else None}


def avaliar_vencedor(run, example):
    esperado = example.outputs or {}
    if esperado.get("estado") != "recomendacao":
        return {"key": "vencedor", "score": None}
    texto = str(_saida(run).get("resposta", ""))
    return {"key": "vencedor", "score": int(esperado["fonte_vencedora"] in texto)}


def avaliar_valor(run, example):
    esperado = example.outputs or {}
    if esperado.get("estado") != "recomendacao":
        return {"key": "valor", "score": None}
    texto = str(_saida(run).get("resposta", ""))
    return {"key": "valor", "score": int(esperado["total_brl"] in texto)}


def avaliar_trajetoria(run, example):
    esperado = example.outputs or {}
    chamadas = _saida(run).get("ferramentas", [])
    return {"key": "trajetoria", "score": int(all(
        ferramenta in chamadas for ferramenta in esperado["ferramentas"]))}


def avaliar_ferramenta_decisiva(run, example):
    """Trajetória mínima: foi chamada a ferramenta que produz a resposta (a última esperada)."""
    esperadas = (example.outputs or {})["ferramentas"]
    if not esperadas:
        return {"key": "ferramenta_decisiva", "score": None}
    return {"key": "ferramenta_decisiva",
            "score": int(esperadas[-1] in _saida(run).get("ferramentas", []))}


def avaliar_primeira_proposta(run, example):
    """Entre os casos que passam pelo agente, a primeira proposta passou na verificação."""
    tentativas = _saida(run).get("verificacoes", [])
    if not tentativas:
        return {"key": "primeira_proposta", "score": None}
    return {"key": "primeira_proposta", "score": int(not tentativas[0]["erros"])}


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--modelo", help="modelo da OpenAI; por padrão PEDRO_MODEL ou gpt-4.1-mini")
    argumentos.add_argument("--saida", type=Path,
                            help="cópia versionável do registro, p. ex. docs/rastros/r29_langsmith_<modelo>.json")
    argumentos.add_argument("--rotulo", default="", help="sufixo do experimento, p. ex. apos-correcao")
    opcoes = argumentos.parse_args()
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("LANGSMITH_API_KEY"):
        raise SystemExit("Faltam OPENAI_API_KEY e LANGSMITH_API_KEY; sem avaliação remota")
    from langchain_openai import ChatOpenAI
    casos = referencias()
    cenario = criar_cenario(Path("storage/evals/catalogos"))
    # Memória nova em cada experimento: se for reutilizada, os episódios de execuções anteriores
    # entram no contexto e mudam a trajetória do agente.
    memoria = Path(f"storage/evals/memoria-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.sqlite3")
    modelo = opcoes.modelo or os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    llm = ChatOpenAI(model=modelo)
    llm.invoke("ping")  # falha aqui, e não em cada caso, se o modelo não estiver disponível
    nli = ModeloNLI()

    def objetivo(entrada: dict) -> dict:
        sessao = nova_sessao(memoria, "avaliacao", cenario.dataset_id)
        rastro = Rastro()
        fluxo = criar_fluxo(cenario, memoria, llm=llm, classificador=nli, rastro=rastro)
        saida = fluxo.invoke({"input": entrada["pergunta"]}, config={"configurable": {
            "user_id": "avaliacao", "session_id": sessao}})
        return {"resposta": saida.content,
                "ferramentas": [e["ferramenta"] for e in rastro.eventos
                                if e["evento"] == "tool_start"],
                "verificacoes": [{"tentativa": e["tentativa"], "estado": e["estado"],
                                  "erros": e["erros"]}
                                 for e in rastro.eventos if e["evento"] == "verificacao"]}

    agora = datetime.now(timezone.utc)
    # O LangSmith precisa que o conjunto de casos exista lá; é criado uma vez e reutilizado.
    cliente = Client()
    impressao = hashlib.sha256(CASOS_CAMINHO.read_bytes()).hexdigest()[:8]
    nome_dataset = f"pedro-infnet-casos-derivados-{impressao}"
    if not cliente.has_dataset(dataset_name=nome_dataset):
        dataset = cliente.create_dataset(
            dataset_name=nome_dataset,
            description="30 casos derivados sintéticos e congelados; não são os casos oficiais.")
        cliente.create_examples(dataset_id=dataset.id, examples=[
            {"inputs": {"pergunta": caso["pergunta"]}, "outputs": caso["esperado"],
             "metadata": {"grupo": caso["grupo"], "caso_id": caso["id"]}} for caso in casos])
    experimento = evaluate(
        objetivo, data=nome_dataset, evaluators=[avaliar_conteudo, avaliar_vencedor,
        avaliar_valor, avaliar_trajetoria, avaliar_ferramenta_decisiva,
        avaliar_primeira_proposta], upload_results=True, max_concurrency=1,
        experiment_prefix=f"pedro-infnet-fluxo-{modelo}" + (f"-{opcoes.rotulo}" if opcoes.rotulo else ""),
        metadata={"dataset_id": cenario.dataset_id, "nli_model": MODELO,
                  "nli_revision": REVISAO, "casos": len(casos), "modelo_llm": modelo})
    resultados = list(experimento)
    linhas = []
    metricas: dict[str, list[int]] = {}
    por_grupo: dict[str, dict[str, list[int]]] = {}
    for linha in resultados:
        scores = {r.key: r.score for r in linha["evaluation_results"]["results"]}
        meta_caso = linha["example"].metadata or {}
        grupo = str(meta_caso.get("grupo"))
        for nome, score in scores.items():
            if score is not None:
                metricas.setdefault(nome, []).append(int(score))
                por_grupo.setdefault(grupo, {}).setdefault(nome, []).append(int(score))
        linhas.append({"caso_id": meta_caso.get("caso_id"),
                       "pergunta": (linha["example"].inputs or {}).get("pergunta"),
                       "grupo": meta_caso.get("grupo"),
                       "run_id": str(linha["run"].id), "saida": linha["run"].outputs,
                       "scores": scores})
    resumo = {k: {"acertos": sum(v), "total": len(v),
                  "taxa": sum(v) / len(v) if v else None}
              for k, v in metricas.items()}
    destino = Path("storage/evals/fluxo.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    registro = json.dumps({
        "data_utc": agora.isoformat(), "modo": "real", "modelo_llm": modelo,
        "rotulo": opcoes.rotulo,
        "memoria": "nova para este experimento",
        "experimento_langsmith": experimento.experiment_name,
        "dataset_langsmith": nome_dataset,
        "dataset_id": cenario.dataset_id, "resumo": resumo,
        "por_grupo": {grupo: {nome: f"{sum(v)}/{len(v)}" for nome, v in metricas_grupo.items()}
                      for grupo, metricas_grupo in por_grupo.items()},
        "casos": linhas}, indent=2, ensure_ascii=False)
    destino.write_text(registro, encoding="utf-8")
    if opcoes.saida:
        opcoes.saida.parent.mkdir(parents=True, exist_ok=True)
        opcoes.saida.write_text(registro + "\n", encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False))
    print(f"experimento {experimento.experiment_name}; registro {opcoes.saida or destino}")


if __name__ == "__main__":
    main()
