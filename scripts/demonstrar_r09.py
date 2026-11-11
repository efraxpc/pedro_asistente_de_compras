"""R09: roteamento dinâmico com RouterChain. Compara o router por regras com o router LLM.

Requer OPENAI_API_KEY. O catálogo é sintético e o ViaCEP é simulado.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.catalog import criar_cenario
from pedro.legacy import DESTINOS, RouterCompras, criar_router_llm, executar_rota

ROOT = Path(__file__).resolve().parents[1]
# pergunta -> rota que uma pessoa escolheria
CASOS = [
    ("preço de PEC-01-0001", "comparacao"),
    ("Busque compressores para geladeira", "catalogo"),
    ("Quanto custa o compressor PEC-01-0001?", "comparacao"),
    ("Quem vende PEC-01-0001 e em quantos dias chega?", "comparacao"),
    ("A que cidade corresponde o CEP 01001-000?", "cep"),
    ("Vocês têm algum termostato em estoque?", "catalogo"),
    ("Olá, bom dia", "esclarecimento"),
]


def _resumo(resultado) -> str:
    if isinstance(resultado, list):
        return f"{len(resultado)} linhas"
    return str(resultado)[:80]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/r09_router_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    cenario = criar_cenario(ROOT / "storage/evidencias/r09_catalogos")
    routers = {"regras": RouterCompras(),
               "llm": criar_router_llm(ChatOpenAI(model=modelo, temperature=0))}
    linhas = []
    acertos = {nome: 0 for nome in routers}
    for pergunta, esperada in CASOS:
        linha: dict[str, str] = {"pergunta": pergunta, "rota_esperada": esperada}
        for nome, router in routers.items():
            execucao = executar_rota(router, cenario, pergunta)
            linha[f"rota_{nome}"] = execucao["rota"]
            linha[f"resultado_{nome}"] = _resumo(execucao["resultado"])
            acertos[nome] += execucao["rota"] == esperada
        linhas.append(linha)
        print(f"{pergunta:52} esperada={esperada:14} regras={linha['rota_regras']:14} llm={linha['rota_llm']}")
    relatorio = {
        "rubrica": "R09", "modo": "router LLM real remoto (OpenAI); router por regras local; ViaCEP simulado",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0, "destinos": DESTINOS,
        "nota": "As rotas esperadas foram fixadas por uma pessoa. Sete casos não são uma medida de exatidão.",
        "acertos": {nome: f"{valor}/{len(CASOS)}" for nome, valor in acertos.items()},
        "casos": linhas,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("acertos", relatorio["acertos"], "| salvo em", saida)


if __name__ == "__main__":
    main()
