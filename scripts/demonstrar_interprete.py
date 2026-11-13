"""Compara as regras do chat com o intérprete com modelo em mensagens difíceis.

Requer OPENAI_API_KEY. Cada caso parte de uma solicitação em andamento (ou de nenhuma) e tem o
resultado correto fixado à mão: se é uma compra e como a solicitação deve ficar.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.catalog import criar_cenario
from pedro.contracts import Solicitacao
from pedro.dialogue import EstadoCompra, criar_interprete, interpretar_compra, interpretar_turno

ROOT = Path(__file__).resolve().parents[1]
EM_ANDAMENTO = {"produto_id": "PEC-01-0001", "quantidade": 2, "prazo_max_dias": 7}
# (há solicitação em andamento, mensagem, resultado esperado: None = não é compra;
#  senão, (quantidade, orcamento_centavos, prazo_max_dias))
CASOS = [
    (True, "Agora que sejam 3 e mantenha o prazo", (3, None, 7)),
    (True, "Suba para meia dúzia", (6, None, 7)),
    (True, "Com quatro já dá", (4, None, 7)),
    (True, "Melhor sem limite de prazo, mas não posso passar de R$ 5.000", (2, 500000, None)),
    (True, "Preciso que chegue em duas semanas no máximo", (2, None, 14)),
    (True, "Esqueça o prazo", (2, None, None)),
    (True, "Dobre a quantidade", (4, None, 7)),
    (True, "Tenho mil e quinhentos reais para isso", (2, 150000, 7)),
    (True, "Como se verifica a compatibilidade elétrica antes de instalar uma peça?", None),
    (True, "A garantia cobre duas peças do mesmo pedido?", None),
    (True, "A que cidade corresponde o CEP 01001000?", None),
    (True, "Obrigado, isso é tudo", None),
    (False, "Compare um par de PEC-01-0002 em 10 dias", (2, None, 10)),
    (False, "Compare PEC-01-0001", (None, None, None)),
]


def _resumo(resultado) -> tuple | None:
    if resultado is None:
        return None
    solicitacao = resultado[0].solicitacao
    return (solicitacao.quantidade, solicitacao.orcamento_centavos, solicitacao.prazo_max_dias)


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/r17_interprete_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    cenario = criar_cenario(ROOT / "storage/evidencias/interprete_catalogos")
    interprete = criar_interprete(ChatOpenAI(model=modelo, temperature=0))
    linhas = []
    acertos = {"regras": 0, "regras_e_modelo": 0}
    for ha_previo, mensagem, esperado in CASOS:
        previo = (EstadoCompra(solicitacao=Solicitacao.model_validate(EM_ANDAMENTO)) if ha_previo else None)
        regras = _resumo(interpretar_compra(cenario, previo, mensagem))
        combinado, leitura = interpretar_turno(cenario, previo, mensagem, interprete)
        com_modelo = _resumo(combinado)
        acertos["regras"] += regras == esperado
        acertos["regras_e_modelo"] += com_modelo == esperado
        linhas.append({"solicitacao_em_andamento": EM_ANDAMENTO if ha_previo else None, "mensagem": mensagem,
                       "esperado": esperado, "regras": regras, "regras_e_modelo": com_modelo,
                       "leitura_do_modelo": leitura.get("modelo")})
        print(f"{mensagem[:62]:62} esperado={str(esperado):22} regras={str(regras):22} "
              f"{'✔' if regras == esperado else '✘'}  +modelo={str(com_modelo):22} "
              f"{'✔' if com_modelo == esperado else '✘'}")
    relatorio = {
        "tema": "intérprete de turno", "modo": "real remoto (OpenAI) para o intérprete; regras locais",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "nota": "Catorze mensagens escolhidas por serem difíceis e rotuladas à mão. Cada resultado é "
                "None (não é compra) ou (quantidade, orçamento em centavos, prazo em dias).",
        "acertos": {nome: f"{valor}/{len(CASOS)}" for nome, valor in acertos.items()},
        "casos": linhas,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("acertos", relatorio["acertos"], "| salvo em", saida)


if __name__ == "__main__":
    main()
