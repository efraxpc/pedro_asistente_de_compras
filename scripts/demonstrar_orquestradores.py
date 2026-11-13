"""O mesmo agente em LangChain clássico e em LangGraph, com o modelo real.

Requer OPENAI_API_KEY e o extra `comparacao` (uv sync --all-extras). Catálogo sintético.
"""
import argparse
import importlib.metadata as md
import inspect
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro import orquestradores
from pedro.catalog import criar_cenario

ROOT = Path(__file__).resolve().parents[1]
TURNOS = ["Busque o compressor com SKU GELA-COMP-0001 e diga o ID dele.",
          "Qual dos fornecedores dele entrega mais rápido e em quantos dias?",
          "E qual é o mais barato com estoque? Diga o preço em reais."]
OUTRO_FIO = "De qual peça estávamos falando?"


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/r07_orquestradores_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    cenario = criar_cenario(ROOT / "storage/evidencias/orquestradores_catalogos")
    resultados = {}
    for nome, construtor in (("LangChain clássico", orquestradores.agente_langchain),
                             ("LangGraph", orquestradores.agente_langgraph)):
        conversar = construtor(ChatOpenAI(model=modelo, temperature=0), cenario)
        turnos = []
        inicio = time.perf_counter()
        for texto in TURNOS:
            turno = conversar(texto, "fio-a")
            turnos.append({"usuario": texto, **turno})
            print(f"{nome:18} | {texto[:44]:44} -> {turno['ferramentas']} | {turno['resposta'][:100]}")
        segundos = time.perf_counter() - inicio
        isolado = conversar(OUTRO_FIO, "fio-b")
        print(f"{nome:18} | outro fio: {isolado['resposta'][:110]}")
        grafo = getattr(conversar, "grafo", None)
        resultados[nome] = {
            "linhas_para_construi_lo": len(inspect.getsource(construtor).splitlines()),
            "memoria": ("RunnableWithMessageHistory + histórico por session_id"
                        if grafo is None else "checkpointer InMemorySaver + thread_id"),
            "nos_do_grafo": None if grafo is None else sorted(grafo.get_graph().nodes),
            "segundos_tres_turnos": round(segundos, 1),
            "turnos": turnos, "outro_fio": {"usuario": OUTRO_FIO, **isolado}}
    relatorio = {
        "tema": "comparação de orquestradores", "modo": "real remoto (OpenAI); catálogo sintético",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "versoes": {p: md.version(p) for p in ("langchain-core", "langchain-classic",
                                               "langchain", "langgraph")},
        "nota": "Mesmo modelo, mesmas duas ferramentas e mesmo prompt. Uma execução por "
                "orquestrador: os tempos não são um benchmark.",
        "orquestradores": resultados,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({n: (r["linhas_para_construi_lo"], r["segundos_tres_turnos"], r["nos_do_grafo"])
           for n, r in resultados.items()})
    print("salvo em", saida)


if __name__ == "__main__":
    main()
