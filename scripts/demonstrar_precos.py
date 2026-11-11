"""Aviso de preço com o modelo real: conselho redigido pelo LLM e verificado com NLI.

Requer OPENAI_API_KEY. Para quinze peças com um aviso de preço, o modelo redige um
conselho a partir dos fatos; registra-se se ele passa na verificação exata e no NLI, ou se
fica o aviso fixo. Depois, uma comparação completa no chat. Catálogo sintético.
"""
import argparse
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Rastro, criar_fluxo
from pedro.catalog import criar_cenario
from pedro.contracts import Solicitacao
from pedro.memory import nova_sessao
from pedro.nli import MODELO, ModeloNLI
from pedro.precos import (LIMIAR_FORTE, LIMIAR_NOTAVEL, aconselhar, aviso_de_preco,
                          criar_conselheiro)
from pedro.verification import resposta_local

ROOT = Path(__file__).resolve().parents[1]
CASOS = 15
NO_CHAT = "Compare 5 unidades de PEC-02-0189"


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/precos_conselho_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    cenario = criar_cenario(ROOT / "storage/evidencias/precos_catalogos")
    llm = ChatOpenAI(model=modelo, temperature=0)
    conselheiro, nli = criar_conselheiro(llm), ModeloNLI()
    with sqlite3.connect(cenario.caminho) as db:
        ids = [linha[0] for linha in db.execute("SELECT id FROM parts ORDER BY id")]
    linhas, fontes, motivos = [], Counter(), Counter()
    total_recomendacoes = com_aviso = 0
    for produto_id in ids:
        comparacao = resposta_local(cenario, Solicitacao(produto_id=produto_id, quantidade=5))
        if comparacao.estado != "recomendacao":
            continue
        total_recomendacoes += 1
        if aviso_de_preco(comparacao) is None:
            continue
        com_aviso += 1
        if len(linhas) >= CASOS:
            continue
        resultado = aconselhar(comparacao, conselheiro, nli)
        fontes[resultado["fonte"]] += 1
        for erro in resultado.get("erros") or []:
            motivos[erro.split("(")[0].strip()] += 1
        linhas.append({"produto_id": produto_id, "fatos": resultado["fatos"],
                       "aviso_fixo": aviso_de_preco(comparacao),
                       "fonte_publicada": resultado["fonte"], "texto_publicado": resultado["texto"],
                       "conselho_rejeitado": resultado.get("conselho_rejeitado"),
                       "erros": resultado.get("erros")})
        print(produto_id, "->", resultado["fonte"], resultado.get("erros") or "")
        print("    ", (resultado.get("conselho_rejeitado") or resultado["texto"])[:230])

    memoria = ROOT / f"storage/evidencias/precos_memoria-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.sqlite3"
    sessao = nova_sessao(memoria, "evidencia_precos", cenario.dataset_id)
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=ChatOpenAI(model=modelo), classificador=nli, rastro=rastro)
    resposta = fluxo.invoke({"input": NO_CHAT}, config={"configurable": {
        "user_id": "evidencia_precos", "session_id": sessao}}).content
    print(resposta)
    relatorio = {
        "tema": "aviso de preço", "rubricas_que_aplica": ["R04", "R06", "R09", "R11", "R12", "R19", "R24"],
        "modo": "real remoto (OpenAI) para o conselho; NLI real local; catálogo sintético",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0, "modelo_nli": MODELO,
        "limiares": {"notavel": LIMIAR_NOTAVEL, "forte": LIMIAR_FORTE},
        "frequencia_do_aviso": {"recomendacoes_para_5_unidades": total_recomendacoes,
                                "com_aviso_de_preco": com_aviso},
        "conselhos": {"casos": len(linhas), "publicado": dict(fontes), "motivos_de_rejeicao": dict(motivos)},
        "nota": "Os primeiros quinze casos com aviso, em ordem de catálogo. Uma execução.",
        "casos": linhas,
        "no_chat": {"usuario": NO_CHAT, "resposta_publicada": resposta,
                    "conselho_preco": [e for e in rastro.eventos if e["evento"] == "conselho_preco"],
                    "ferramentas": [e["ferramenta"] for e in rastro.eventos if e["evento"] == "tool_start"]},
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio["frequencia_do_aviso"], relatorio["conselhos"]["publicado"],
          relatorio["conselhos"]["motivos_de_rejeicao"])
    print("salvo em", saida)


if __name__ == "__main__":
    main()
