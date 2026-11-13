"""Agente ReAct clássico (initialize_agent) com o modelo real, ferramentas e memória.

Requer OPENAI_API_KEY. Executa a mesma conversa de dois turnos duas vezes: com o
histórico dentro do prompt e sem ele. O catálogo é sintético.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.catalog import criar_cenario
from pedro.legacy import criar_react_textual

ROOT = Path(__file__).resolve().parents[1]
TURNOS = ["Busque o compressor com SKU GELA-COMP-0001 e diga o ID dele.",
          "Qual dos fornecedores dele entrega mais rápido e em quantos dias?"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/r08_react_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    cenario = criar_cenario(ROOT / "storage/evidencias/react_catalogos")
    conversas = {}
    for nome, com_memoria in (("com_historico_no_prompt", True),
                              ("sem_historico_no_prompt", False)):
        agente, memoria = criar_react_textual(ChatOpenAI(model=modelo, temperature=0), cenario,
                                              memoria_no_prompt=com_memoria)
        turnos = []
        for pergunta in TURNOS:
            resultado = agente.invoke({"input": pergunta})
            passos: list[dict[str, str]] = [
                {"raciocinio_e_acao": acao.log.strip(), "ferramenta": acao.tool,
                 "entrada": str(acao.tool_input), "observacao": str(observacao)[:400]}
                for acao, observacao in resultado["intermediate_steps"]]
            turnos.append({"pergunta": pergunta, "passos": passos, "resposta": resultado["output"]})
            print(nome, "|", pergunta, "->",
                  [passo["ferramenta"] + "(" + passo["entrada"] + ")" for passo in passos],
                  "|", str(resultado["output"])[:160])
        conversas[nome] = {
            "variaveis_do_prompt": sorted(agente.agent.llm_chain.prompt.input_variables),
            "turnos": turnos,
            "memoria_salva": memoria.load_memory_variables({})["chat_history"]}
    relatorio = {
        "tema": "agente ReAct clássico", "modo": "real remoto (OpenAI); catálogo sintético",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "agente": "initialize_agent + AgentType.ZERO_SHOT_REACT_DESCRIPTION + ConversationBufferMemory",
        "ferramentas": ["buscar_peca", "ofertas_da_peca"],
        "conversas": conversas,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("salvo em", saida)


if __name__ == "__main__":
    main()
