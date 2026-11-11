"""R10: o agente chama uma API externa real (ViaCEP) por function calling.

Requer OPENAI_API_KEY e acesso a viacep.com.br. Salva o esquema que o modelo recebe,
os argumentos que o modelo envia, a resposta da API e o que é publicado.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.utils.function_calling import convert_to_openai_tool

from pedro.agent import Rastro, criar_fluxo, ferramentas
from pedro.catalog import criar_cenario
from pedro.memory import nova_sessao
from pedro.nli import ModeloNLI

ROOT = Path(__file__).resolve().parents[1]
PERGUNTAS = ["Vou receber o pedido no CEP 01001000. A que cidade e estado ele corresponde?",
             "E o CEP 99999999?",
             "E o CEP 123?"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/r10_viacep_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    cenario = criar_cenario(ROOT / "storage/evidencias/r10_catalogos")
    memoria = ROOT / "storage/evidencias/r10_memoria.sqlite3"
    ferramenta = next(f for f in ferramentas(cenario, memoria, "evidencia_r10", "")
                      if f.name == "consultar_cep")
    sessao = nova_sessao(memoria, "evidencia_r10", cenario.dataset_id)
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=ChatOpenAI(model=modelo), classificador=ModeloNLI(),
                        rastro=rastro)
    turnos = []
    for pergunta in PERGUNTAS:
        desde = len(rastro.eventos)
        resposta = fluxo.invoke({"input": pergunta}, config={"configurable": {
            "user_id": "evidencia_r10", "session_id": sessao}}).content
        eventos = rastro.eventos[desde:]
        chamadas = [{"ferramenta": inicio["ferramenta"], "argumentos_do_modelo": inicio["entrada"],
                     "resposta_da_api": fim["resultado"]}
                    for inicio, fim in zip([e for e in eventos if e["evento"] == "tool_start"],
                                           [e for e in eventos if e["evento"] == "tool_end"])]
        turnos.append({"pergunta": pergunta, "chamadas": chamadas,
                       "verificacoes": [{"tentativa": e["tentativa"], "erros": e["erros"]}
                                        for e in eventos if e["evento"] == "verificacao"],
                       "resposta_publicada": resposta})
        print(pergunta, "->", [(c["argumentos_do_modelo"], c["resposta_da_api"][:90])
                               for c in chamadas], "|", str(resposta)[:90])
    relatorio = {
        "rubrica": "R10", "modo": "real remoto: OpenAI e ViaCEP (https://viacep.com.br)",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo,
        "esquema_enviado_ao_modelo": convert_to_openai_tool(ferramenta),
        "turnos": turnos,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("salvo em", saida)


if __name__ == "__main__":
    main()
