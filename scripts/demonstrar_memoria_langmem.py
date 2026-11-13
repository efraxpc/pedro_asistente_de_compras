"""A mesma conversa com a memória própria do Pedro e com o LangMem.

Requer OPENAI_API_KEY e o extra `comparacao`. Compara o que cada uma salva, quem decide
salvar e o que se recupera em outra sessão e para outro usuário. Catálogo sintético.
"""
import argparse
import importlib.metadata as md
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Rastro, criar_fluxo
from pedro.catalog import criar_cenario
from pedro.memory import MODELO_LEMBRANCAS, nova_sessao, preferencias
from pedro.nli import ModeloNLI
from pedro.orquestradores import agente_com_langmem

ROOT = Path(__file__).resolve().parents[1]
SESSAO_1 = ["Prefiro fornecedores nacionais, lembre-se disso.",
            "Compare 5 unidades de PEC-01-0001 com prazo de 7 dias.",
            "Ufa, acho que esse compressor vai sair caro para mim. Minha oficina é pequena."]
SESSAO_2 = "O que você lembra das minhas preferências?"


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/r15_memoria_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    cenario = criar_cenario(ROOT / "storage/evidencias/memoria_langmem_catalogos")

    # --- Memória própria do Pedro ---
    memoria = ROOT / f"storage/evidencias/memoria_langmem_memoria-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.sqlite3"
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=ChatOpenAI(model=modelo), classificador=ModeloNLI(),
                        rastro=rastro)
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    turnos_pedro = []
    for texto in SESSAO_1:
        desde = len(rastro.eventos)
        resposta = fluxo.invoke({"input": texto}, config={"configurable": {
            "user_id": "ana", "session_id": sessao}}).content
        turnos_pedro.append({"usuario": texto, "resposta": resposta.splitlines()[0],
                             "ferramentas": [e["ferramenta"] for e in rastro.eventos[desde:]
                                             if e["evento"] == "tool_start"]})
        print("Pedro   |", texto[:50], "->", turnos_pedro[-1]["ferramentas"], "|", resposta.splitlines()[0][:90])
    nova_sessao(memoria, "luis", cenario.dataset_id)
    with sqlite3.connect(memoria) as db:
        episodios = [linha[0][:140] for linha in db.execute(
            "SELECT texto FROM episodios WHERE user_id='ana' ORDER BY id")]
    pedro = {"turnos": turnos_pedro,
             "salvo_para_ana": {"preferencias": preferencias(memoria, "ana"), "episodios": episodios},
             "salvo_para_outro_usuario": {"preferencias": preferencias(memoria, "luis")},
             "quem_decide": "o código: uma preferência só com citação literal do usuário; um "
                            "episódio só após uma resposta de compra verificada"}

    # --- LangMem ---
    embeddings = FastEmbedEmbeddings(model_name=MODELO_LEMBRANCAS, doc_embed_type="passage")
    conversar, armazem = agente_com_langmem(ChatOpenAI(model=modelo, temperature=0), cenario,
                                            embeddings, 384)
    turnos_langmem = []
    for texto in SESSAO_1:
        turno = conversar(texto, "ana", "sessao-1")
        turnos_langmem.append({"usuario": texto, **turno})
        print("LangMem |", texto[:50], "->", [f.split("(")[0] for f in turno["ferramentas"]], "|",
              turno["resposta"][:90])
    outra_sessao = conversar(SESSAO_2, "ana", "sessao-2")
    outro_usuario = conversar(SESSAO_2, "luis", "sessao-3")
    print("LangMem | sessão nova:", outra_sessao["resposta"][:160])
    print("LangMem | outro usuário:", outro_usuario["resposta"][:160])
    langmem = {"turnos": turnos_langmem,
               "salvo_para_ana": [item.value for item in armazem.search(("lembrancas", "ana"))],
               "salvo_para_outro_usuario": [item.value for item in armazem.search(("lembrancas", "luis"))],
               "sessao_nova": {"usuario": SESSAO_2, **outra_sessao},
               "outro_usuario": {"usuario": SESSAO_2, **outro_usuario},
               "quem_decide": "o modelo, com as ferramentas manage_memory e search_memory"}
    print("Pedro salvou:", pedro["salvo_para_ana"]["preferencias"], "e", len(episodios), "episódio(s)")
    print("LangMem salvou:", langmem["salvo_para_ana"])

    relatorio = {
        "tema": "memória própria e LangMem", "modo": "real remoto (OpenAI); embeddings reais locais; catálogo sintético",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo,
        "versoes": {p: md.version(p) for p in ("langmem", "langgraph", "langchain")},
        "nota": "A mesma conversa de três mensagens nos dois sistemas. Uma execução: o que "
                "o modelo decide salvar com o LangMem pode variar de uma execução para outra.",
        "memoria_propria_do_pedro": pedro, "langmem": langmem,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("salvo em", saida)


if __name__ == "__main__":
    main()
