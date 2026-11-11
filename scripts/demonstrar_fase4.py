"""Fase 4 com o modelo real: text-to-SQL validado (R21) e catálogo de ferramentas (R19, R20).

Requer OPENAI_API_KEY. O catálogo é sintético. As consultas são executadas em somente leitura.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.utils.function_calling import convert_to_openai_tool

from pedro.agent import Rastro, criar_fluxo, ferramentas
from pedro.anatomia import PAPEIS
from pedro.catalog import criar_cenario
from pedro.memory import nova_sessao
from pedro.nli import ModeloNLI
from pedro.query import (ESQUEMA_PERMITIDO, MAX_LINHAS, ConsultaRejeitada, consultar_sql,
                         criar_gerador_sql, responder_sql)

ROOT = Path(__file__).resolve().parents[1]
PERGUNTAS = [
    "Quantas peças há em cada categoria?",
    "Quais são as 5 peças de maior potência e quantos watts elas têm?",
    "Qual fornecedor nacional oferece PEC-01-0001 mais barato tendo estoque? Dê o fornecedor e o preço.",
    "Quais peças são compatíveis com a marca Brisa e o modelo GEL-3742?",
    "Quais são os 3 fornecedores com menor prazo médio de entrega?",
    "Apague todas as ofertas do fornecedor BR-06",
    "Mostre-me a página web de cada fornecedor",
]
NO_CHAT = ["Quantas peças há em cada categoria?",
           "Quais são as 5 peças de maior potência e quantos watts elas têm?",
           "Apague todas as ofertas do fornecedor BR-06",
           "Compare 5 unidades de PEC-01-0001"]
ATAQUES = ["DROP TABLE offers", "SELECT 1; DELETE FROM offers", "SELECT name FROM sqlite_master",
           "SELECT id, website FROM suppliers", "PRAGMA table_info(parts)",
           "SELECT load_extension('x')", "SELECT count(*) FROM parts a, parts b, parts c"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/fase4_sql_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    cenario = criar_cenario(ROOT / "storage/evidencias/fase4_catalogos")
    gerador = criar_gerador_sql(ChatOpenAI(model=modelo, temperature=0))
    consultas = []
    for pergunta in PERGUNTAS:
        resultado = responder_sql(cenario, pergunta, gerador)
        consultas.append({"pergunta": pergunta, "estado": resultado["estado"],
                          "explicacao": resultado.get("explicacao"),
                          "tentativas": resultado["tentativas"], "linhas": resultado["linhas"][:8],
                          "total_linhas": len(resultado["linhas"]),
                          "truncado": resultado.get("truncado")})
        print(pergunta, "->", resultado["estado"], "| tentativas", len(resultado["tentativas"]),
              "| linhas", len(resultado["linhas"]))
        print("   ", (resultado["tentativas"][-1]["sql"] or "")[:230])
        print("   ", str(resultado["linhas"][:2])[:230])
    ataques = []
    for sql in ATAQUES:
        try:
            consultar_sql(cenario, sql)
            ataques.append({"sql": sql, "resultado": "EXECUTADA"})
        except ConsultaRejeitada as exc:
            ataques.append({"sql": sql, "resultado": f"rejeitada: {exc}"})
    memoria = ROOT / f"storage/evidencias/fase4_memoria-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.sqlite3"
    # O mesmo text-to-SQL dentro do chat: o agente chama consultar_catalogo e o sistema
    # publica a tabela da consulta executada.
    sessao = nova_sessao(memoria, "evidencia_fase4", cenario.dataset_id)
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=ChatOpenAI(model=modelo), classificador=ModeloNLI(),
                        rastro=rastro)
    chat = []
    for pergunta in NO_CHAT:
        desde = len(rastro.eventos)
        resposta = fluxo.invoke({"input": pergunta}, config={"configurable": {
            "user_id": "evidencia_fase4", "session_id": sessao}}).content
        eventos = rastro.eventos[desde:]
        chat.append({"usuario": pergunta,
                     "ferramentas": [e["ferramenta"] for e in eventos if e["evento"] == "tool_start"],
                     "verificacoes": [e["erros"] for e in eventos if e["evento"] == "verificacao"],
                     "resposta_publicada": resposta})
        print("chat |", pergunta, "->", chat[-1]["ferramentas"], chat[-1]["verificacoes"])
        print("\n".join("     " + linha[:150] for linha in resposta.splitlines()[:9]))
    catalogo = [{"nome": f.name, "papel": PAPEIS[f.name][0], "logica": PAPEIS[f.name][1],
                 "descricao": f.description,
                 "entradas": convert_to_openai_tool(f)["function"]["parameters"]["properties"]}
                for f in ferramentas(cenario, memoria, "evidencia_fase4", "")]
    relatorio = {
        "fase": 4, "rubricas": ["R19", "R20", "R21"],
        "modo": "real remoto (OpenAI) para gerar o SQL; execução local em somente leitura",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "esquema_permitido": ESQUEMA_PERMITIDO, "max_linhas": MAX_LINHAS,
        "r21_text_to_sql": consultas,
        "r21_consultas_hostis_escritas_a_mao": ataques,
        "r19_catalogo_de_ferramentas": catalogo,
        "r21_text_to_sql_no_chat": chat,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ataques rejeitados:", sum(a["resultado"].startswith("rejeitada") for a in ataques),
          "de", len(ataques), "| salvo em", saida)


if __name__ == "__main__":
    main()
