"""R23 no chat: a falha de recuperação corrigida e uma resposta à pergunta que foi feita.

Requer OPENAI_API_KEY. Várias perguntas diferentes sobre receber um pedido em várias caixas.
Todas passam pela mesma recuperação corrigida (a reformulação leva a regra à posição 1) e
citam a mesma regra literal; o que muda é a frase que responde a cada pergunta. Salva, para
cada pergunta, a recuperação antes e depois, a decisão do modelo, a frase publicada ou
descartada e os erros de verificação.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from pedro.agent import Rastro, criar_fluxo
from pedro.catalog import criar_cenario
from pedro.memory import nova_sessao
from pedro.nli import ModeloNLI
from pedro.policy_demo import FRAGMENTO_T24_ESPERADO, criar_indice_demo

ROOT = Path(__file__).resolve().parents[1]
PERGUNTAS = ["Posso receber em várias caixas?",
             "Quais produtos posso receber em várias caixas?",
             "Quanto custa receber o pedido em duas caixas?",
             "Sem um acordo, o pedido pode chegar em caixas separadas?",
             "O pedido pode chegar em vários pacotes de fornecedores diferentes?"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/r23_resposta_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    cenario = criar_cenario(ROOT / "storage/evidencias/r23_catalogos")
    memoria = ROOT / f"storage/evidencias/r23_memoria-{marca}.sqlite3"
    sessao = nova_sessao(memoria, "evidencia_r23", cenario.dataset_id)
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=ChatOpenAI(model=modelo), classificador=ModeloNLI(),
                        indice=criar_indice_demo(), rastro=rastro)
    turnos: list[dict[str, Any]] = []
    for pergunta in PERGUNTAS:
        desde = len(rastro.eventos)
        publicada = fluxo.invoke({"input": pergunta}, config={"configurable": {
            "user_id": "evidencia_r23", "session_id": sessao}}).content
        eventos = rastro.eventos[desde:]
        direta = next((e for e in eventos if e["evento"] == "resposta_politica"), {})
        turnos.append({
            "pergunta": pergunta,
            "ferramentas": [e["ferramenta"] for e in eventos if e["evento"] == "tool_start"],
            "resposta_do_modelo": {chave: direta.get(chave) for chave in
                                   ("fonte", "responde", "texto", "rejeitada", "erros")},
            "cita_a_regra": FRAGMENTO_T24_ESPERADO in publicada,
            "mostra_a_recuperacao_corrigida": "Recuperação T24" in publicada,
            "resposta_publicada": publicada,
        })
        print(f"{pergunta}\n   {direta.get('fonte')} | responde={direta.get('responde')} | "
              f"{publicada.splitlines()[0][:230]}")
        if direta.get("erros"):
            print("   descartada:", direta.get("rejeitada"), "|", direta["erros"])
    primeiras = {t["resposta_publicada"].split("\n")[0] for t in turnos}
    relatorio = {
        "rubrica": "R23",
        "modo": "real remoto: OpenAI; NLI real local; índice fictício de demonstração em memória",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo,
        "resumo": {"perguntas": len(turnos),
                   "resposta_verificada": sum(t["resposta_do_modelo"]["fonte"] == "resposta verificada"
                                              for t in turnos),
                   "regra_literal": sum(t["resposta_do_modelo"]["fonte"] == "regra literal" for t in turnos),
                   "citam_a_regra": sum(t["cita_a_regra"] for t in turnos),
                   "mostram_a_recuperacao_corrigida": sum(t["mostra_a_recuperacao_corrigida"]
                                                          for t in turnos),
                   "primeiras_linhas_diferentes": len(primeiras)},
        "turnos": turnos,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio["resumo"], "| salvo em", saida)


if __name__ == "__main__":
    main()
