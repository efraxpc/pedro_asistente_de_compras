"""R22: agente de recuperação sobre o índice FAISS já salvo em knowledge/politicas/.

Não constrói o índice: carrega-o com `carregar_indice` após conferir o manifesto e as
impressões digitais. Requer OPENAI_API_KEY para as perguntas ao agente; o corpus é fictício.
"""
import argparse
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Rastro, criar_fluxo, ferramentas
from pedro.catalog import criar_cenario
from pedro.memory import nova_sessao
from pedro.nli import ModeloNLI
from pedro.rag import carregar_indice, inspecionar_indice

ROOT = Path(__file__).resolve().parents[1]
PASTA = ROOT / "knowledge/politicas"
PERGUNTAS = ["Como se verifica a compatibilidade elétrica antes de instalar uma peça?",
             "Posso receber em várias caixas?"]


def _erro(acao) -> str:
    try:
        acao()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return "sem erro"


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path,
                            default=ROOT / "docs/rastros/r22_indice_existente.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_openai import ChatOpenAI

    manifesto = inspecionar_indice(PASTA)
    embeddings = FastEmbedEmbeddings(model_name=manifesto["embedding_model"],
                                     doc_embed_type="passage")
    # A porta de segurança: sem confiança explícita ou com um arquivo alterado, não se carrega.
    sem_confianca = _erro(lambda: carregar_indice(PASTA, embeddings, origem_confiavel=False))
    with tempfile.TemporaryDirectory() as temporario:
        copia = Path(temporario) / "politicas"
        shutil.copytree(PASTA, copia)
        with (copia / "index.pkl").open("ab") as arquivo:
            arquivo.write(b"alterado")
        alterado = _erro(lambda: carregar_indice(copia, embeddings, origem_confiavel=True))

    inicio = time.perf_counter()
    indice, _ = carregar_indice(PASTA, embeddings, origem_confiavel=True)
    segundos_carga = time.perf_counter() - inicio

    cenario = criar_cenario(ROOT / "storage/evidencias/r22_catalogos")
    # Memória nova a cada execução: as lembranças de execuções anteriores mudavam o resultado.
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    memoria = ROOT / f"storage/evidencias/r22_memoria-{marca}.sqlite3"
    ferramenta = next(f for f in ferramentas(cenario, memoria, "evidencia_r22", "", indice)
                      if f.name == "consultar_politicas")
    direta = json.loads(ferramenta.invoke({"pergunta": PERGUNTAS[0]}))

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    sessao = nova_sessao(memoria, "evidencia_r22", cenario.dataset_id)
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=ChatOpenAI(model=modelo), classificador=ModeloNLI(),
                        indice=indice, rastro=rastro)
    turnos = []
    for pergunta in PERGUNTAS:
        desde = len(rastro.eventos)
        resposta = fluxo.invoke({"input": pergunta}, config={"configurable": {
            "user_id": "evidencia_r22", "session_id": sessao}}).content
        eventos = rastro.eventos[desde:]
        turnos.append({
            "pergunta": pergunta,
            "ferramentas": [e["ferramenta"] for e in eventos if e["evento"] == "tool_start"],
            "citacoes_ancoradas": [c for e in eventos if e["evento"] == "citacoes_ancoradas"
                                   for c in e["citacoes"]],
            "verificacoes": [{"tentativa": e["tentativa"], "estado": e["estado"], "erros": e["erros"]}
                             for e in eventos if e["evento"] == "verificacao"],
            "resposta_publicada": resposta})

    relatorio = {
        "rubrica": "R22",
        "modo": "índice carregado do disco; agente real remoto (OpenAI); NLI real local; corpus fictício",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "indice": {"pasta": str(PASTA.relative_to(ROOT)), "origem": manifesto["origem"],
                   "criado_utc": manifesto.get("criado_utc"),
                   "embedding_model": manifesto["embedding_model"],
                   "dimension": manifesto["dimension"], "metrica": manifesto["metrica"],
                   "fragmentos": indice.index.ntotal, "sha256": manifesto["sha256"],
                   "segundos_de_carga": round(segundos_carga, 2)},
        "porta_de_seguranca": {"sem_confianca_explicita": sem_confianca,
                               "copia_com_index_pkl_alterado": alterado},
        "ferramenta_consultar_politicas": {
            "pergunta": PERGUNTAS[0],
            "fragmentos": [{"posicao": f["posicao"], "fonte_id": f["fonte_id"],
                            "secao": f["metadados"]["secao"], "distancia_l2": round(f["score"], 3)}
                           for f in direta["fragmentos"]]},
        "agente": {"modelo_llm": modelo, "turnos": turnos},
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("carga:", relatorio["indice"]["fragmentos"], "fragmentos em", relatorio["indice"]["segundos_de_carga"], "s")
    print("porta:", sem_confianca, "|", alterado)
    print("ferramenta:", [f["fonte_id"] for f in relatorio["ferramenta_consultar_politicas"]["fragmentos"]])
    for turno in turnos:
        print(turno["pergunta"], "->", turno["ferramentas"], turno["citacoes_ancoradas"])
        print("   ", str(turno["resposta_publicada"])[:260].replace("\n", " / "))
    print("salvo em", saida)


if __name__ == "__main__":
    main()
