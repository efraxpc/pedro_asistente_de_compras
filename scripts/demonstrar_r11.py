"""R11: mede três técnicas de prompt na mesma extração: zero-shot, few-shot e few-shot + CoT.

Requer OPENAI_API_KEY. Dez solicitações difíceis, com a resposta correta fixada à mão.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.chains import criar_variantes_de_prompt

ROOT = Path(__file__).resolve().parents[1]
CAMPOS = ("produto_id", "quantidade", "orcamento_centavos", "prazo_max_dias")
# solicitação -> (quantidade, orçamento em centavos, prazo em dias); None significa «não diz»
CASOS = [
    ("Preciso de meia dúzia de PEC-01-0001", "PEC-01-0001", 6, None, None),
    ("Compare PEC-02-0003, um par, até mil e quinhentos reais", "PEC-02-0003", 2, 150000, None),
    ("Quero 3 de PEC-01-0002 para daqui a duas semanas", "PEC-01-0002", 3, None, 14),
    ("Me dê 4 unidades de PEC-03-0001, sem limite de orçamento, em 10 dias", "PEC-03-0001", 4, None, 10),
    ("PEC-01-0001: duas unidades... não, melhor três. Teto de R$ 2.000", "PEC-01-0001", 3, 200000, None),
    ("Quanto sairiam 5 PEC-04-0002 se não posso gastar mais de R$ 1.234,56?", "PEC-04-0002", 5, 123456, None),
    ("Compare PEC-05-0001 com R$ 800 de orçamento", "PEC-05-0001", None, 80000, None),
    ("Preciso de 10 PEC-06-0001 em uma semana no máximo, gasto livre", "PEC-06-0001", 10, None, 7),
    ("Uma dúzia de PEC-07-0001 por R$ 3 mil em um mês", "PEC-07-0001", 12, 300000, 30),
    ("Compre 2 de PEC-08-0001; o prazo tanto faz e tenho R$ 0 disponíveis", "PEC-08-0001", 2, 0, None),
]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/r11_prompts_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    variantes = criar_variantes_de_prompt(ChatOpenAI(model=modelo, temperature=0))
    entradas = [{"texto": caso[0]} for caso in CASOS]
    resumo: dict = {}
    detalhe: list[dict] = []
    saidas = {nome: cadeia.batch(entradas, return_exceptions=True)
              for nome, cadeia in variantes.items()}
    for indice, (texto, *esperado) in enumerate(CASOS):
        linha: dict = {"solicitacao": texto, "esperado": dict(zip(CAMPOS, esperado))}
        for nome in variantes:
            resultado = saidas[nome][indice]
            if isinstance(resultado, Exception):
                linha[nome] = {"erro": type(resultado).__name__, "campos_corretos": 0,
                               "tudo_correto": False}
                continue
            obtido = {campo: getattr(resultado.solicitacao, campo) for campo in CAMPOS}
            corretos = sum(obtido[campo] == linha["esperado"][campo] for campo in CAMPOS)
            linha[nome] = {"obtido": obtido, "campos_corretos": corretos,
                           "tudo_correto": corretos == len(CAMPOS),
                           "raciocinio": getattr(resultado, "raciocinio", None)}
        detalhe.append(linha)
    for nome in variantes:
        resumo[nome] = {
            "solicitacoes_corretas": f"{sum(f[nome]['tudo_correto'] for f in detalhe)}/{len(CASOS)}",
            "campos_corretos": f"{sum(f[nome]['campos_corretos'] for f in detalhe)}/{len(CASOS) * len(CAMPOS)}"}
    relatorio = {
        "rubrica": "R11", "modo": "real remoto (OpenAI); solicitações sintéticas",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo, "temperature": 0,
        "nota": "Dez casos escolhidos por serem difíceis e rotulados à mão: não são uma amostra representativa.",
        "resumo": resumo, "casos": detalhe,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for linha in detalhe:
        print(f"{linha['solicitacao'][:58]:58}", {n: linha[n]["campos_corretos"] for n in variantes})
    print(json.dumps(resumo, ensure_ascii=False))
    print("salvo em", saida)


if __name__ == "__main__":
    main()
