"""Resposta direta: o agente responde à pergunta feita sobre a comparação, não só repete a tabela.

Requer OPENAI_API_KEY. Uma conversa real: uma comparação e várias perguntas sobre ela. Salva,
para cada pergunta, a frase publicada, se veio do modelo (verificada) ou do resumo fixo, e os
erros de verificação quando a frase do modelo foi descartada.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Rastro, criar_fluxo, partes_de
from pedro.catalog import criar_cenario
from pedro.memory import nova_sessao
from pedro.nli import ModeloNLI

ROOT = Path(__file__).resolve().parents[1]
TURNOS = ["Compare 5 unidades de PEC-01-0001 com prazo de 7 dias",
          "a mais barata?",
          "qual é a mais em conta?",
          "qual chega mais rápido?",
          "por que não a Litoral Parts?",
          "e a Atlantic, quanto custa?",
          "alguma é internacional?"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/pergunta_direta_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    cenario = criar_cenario(ROOT / "storage/evidencias/pergunta_catalogos")
    memoria = ROOT / f"storage/evidencias/pergunta_memoria-{marca}.sqlite3"
    sessao = nova_sessao(memoria, "evidencia_pergunta", cenario.dataset_id)
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=ChatOpenAI(model=modelo), classificador=ModeloNLI(),
                        rastro=rastro)
    turnos = []
    for mensagem in TURNOS:
        desde = len(rastro.eventos)
        publicada = fluxo.invoke({"input": mensagem}, config={"configurable": {
            "user_id": "evidencia_pergunta", "session_id": sessao}})
        eventos = rastro.eventos[desde:]
        direta = next((e for e in eventos if e["evento"] == "resposta_direta"), None)
        parte = partes_de(publicada)[0]
        comparacao = parte.get("comparacao") or {}
        turnos.append({
            "mensagem": mensagem,
            "ferramentas": [e["ferramenta"] for e in eventos if e["evento"] == "tool_start"],
            "resposta_direta": direta and {chave: direta.get(chave) for chave in
                                           ("fonte", "texto", "rejeitada", "erros")},
            "fornecedor_recomendado": comparacao.get("fornecedor_id"),
            "total_centavos": comparacao.get("total_centavos"),
            "primeira_linha_publicada": publicada.content.splitlines()[0],
        })
        print(f"{mensagem!r}\n   -> {direta['fonte'] if direta else 'sem resposta direta'}: "
              f"{publicada.content.splitlines()[0]}")
        if direta and direta.get("erros"):
            print("      descartada:", direta.get("rejeitada"), "|", direta["erros"])
    perguntas = [t for t in turnos if t["resposta_direta"]]
    relatorio = {
        "tema": "resposta direta a perguntas sobre a comparação",
        "modo": "real remoto: OpenAI; NLI real local",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo,
        "resumo": {"perguntas": len(perguntas),
                   "resposta_verificada": sum(t["resposta_direta"]["fonte"] == "resposta verificada"
                                              for t in perguntas),
                   "resumo_fixo": sum(t["resposta_direta"]["fonte"] == "resumo fixo" for t in perguntas)},
        "turnos": turnos,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio["resumo"], "| salvo em", saida)


if __name__ == "__main__":
    main()
