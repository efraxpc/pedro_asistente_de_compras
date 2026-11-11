"""R02: planejamento com o modelo real. Salva a trajetória de ferramentas observada.

Requer OPENAI_API_KEY. Chama a OpenAI e o ViaCEP reais; o catálogo e as políticas são
sintéticos. Não simula resultados: se faltar a chave, termina sem escrever nada.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Rastro, criar_fluxo
from pedro.catalog import criar_cenario
from pedro.memory import nova_sessao
from pedro.nli import MODELO, REVISAO, ModeloNLI
from pedro.policy_demo import ORIGEM, criar_indice_demo

ROOT = Path(__file__).resolve().parents[1]
MISTA = ("Compare 5 unidades de PEC-01-0001 com prazo de 7 dias e diga o que a política de "
         "devoluções diz sobre peças danificadas, e confirme o CEP 01001000")
POR_TURNOS = ["Compare 5 unidades de PEC-01-0001 com prazo de 7 dias",
              "O que a política de devoluções diz sobre peças danificadas?",
              "Confirme o CEP 01001000",
              "agora 6 unidades"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path,
                            default=ROOT / "docs/rastros/r02_planejamento_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    cenario = criar_cenario(ROOT / "storage/evidencias/r02_catalogos")
    memoria = ROOT / "storage/evidencias/r02_memoria.sqlite3"
    llm, nli, indice = ChatOpenAI(model=modelo), ModeloNLI(), criar_indice_demo()

    def conversar(turnos: list[str]) -> list[dict]:
        sessao = nova_sessao(memoria, "evidencia_r02", cenario.dataset_id)
        rastro = Rastro()
        fluxo = criar_fluxo(cenario, memoria, llm=llm, classificador=nli, indice=indice,
                            rastro=rastro)
        registro = []
        for pergunta in turnos:
            inicio = len(rastro.eventos)
            resposta = fluxo.invoke({"input": pergunta}, config={"configurable": {
                "user_id": "evidencia_r02", "session_id": sessao}}).content
            eventos = rastro.eventos[inicio:]
            registro.append({
                "pergunta": pergunta,
                "plano": next((e["pedidos"] for e in eventos if e["evento"] == "plano"), None),
                "ferramentas": [{"nome": e["ferramenta"], "argumentos": e["entrada"]}
                                for e in eventos if e["evento"] == "tool_start"],
                "erros_de_execucao": [e["tipo"] for e in eventos if "error" in e["evento"]],
                "verificacoes": [e["erros"] for e in eventos if e["evento"] == "verificacao"],
                "citacoes_ancoradas": [c for e in eventos if e["evento"] == "citacoes_ancoradas"
                                       for c in e["citacoes"]],
                "resposta_publicada": resposta,
            })
        return registro

    relatorio = {
        "rubrica": "R02",
        "modo": "real remoto (OpenAI e ViaCEP); NLI real local; dados sintéticos",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "modelo_nli": MODELO, "revisao_nli": REVISAO,
        "dataset_id": cenario.dataset_id, "origem_politicas": ORIGEM,
        "nota": "Cada turno admite até duas propostas do agente; a lista de ferramentas "
                "inclui as de ambas. A trajetória depende do modelo e pode variar.",
    }
    blocos = {"solicitacao_mista_em_um_turno": conversar([MISTA]),
              "solicitacao_repartida_em_turnos": conversar(POR_TURNOS)}
    relatorio.update(blocos)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for bloco, turnos in blocos.items():
        print(bloco)
        for turno in turnos:
            print(" ", turno["pergunta"][:60], "->", [f["nome"] for f in turno["ferramentas"]])
            for linha in turno["resposta_publicada"].splitlines()[:14]:
                print("    ", linha[:120])
    print("salvo em", saida)


if __name__ == "__main__":
    main()
