"""Fase 1 com o modelo real: modelo de prompt, saída estruturada, invoke, batch e stream.

Requer OPENAI_API_KEY. Chama a OpenAI; as solicitações são sintéticas. Não simula
resultados: se faltar a chave, termina sem escrever nada.
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.chains import (PROMPT, criar_chain, criar_chain_robusta, criar_lcel,
                          criar_lcel_parcial)
from pedro.contracts import Extracao
from pedro.laboratorio import DADOS, SOLICITACAO, ensaiar

ROOT = Path(__file__).resolve().parents[1]
SOLICITACOES = [
    "Compare 2 unidades de PEC-01-0001 até R$ 5.000 em 7 dias",
    "Preciso de um termostato para geladeira, sem pressa",
    "A que cidade corresponde o CEP 01001000?",
]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path,
                            default=ROOT / "docs/rastros/fase1_chain_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_openai import ChatOpenAI

    nome = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    modelo = ChatOpenAI(model=nome, temperature=0)
    lcel, decorada = criar_lcel(modelo), criar_chain(modelo)
    entradas = [{"texto": texto} for texto in SOLICITACOES]

    um = lcel.invoke(entradas[0])
    imperativa = decorada.invoke(entradas[0])
    # R05: as mesmas três entradas, uma por uma e em lote.
    inicio = time.perf_counter()
    em_serie = [lcel.invoke(entrada) for entrada in entradas]
    segundos_serie = time.perf_counter() - inicio
    inicio = time.perf_counter()
    lote = lcel.batch(entradas)
    segundos_lote = time.perf_counter() - inicio
    # R05: stream sobre uma cadeia que transmite (JSON parcial) e sobre uma que não (Pydantic).
    inicio = time.perf_counter()
    estados, primeiro_estado = [], 0.0
    for estado in criar_lcel_parcial(modelo).stream(entradas[0]):
        if not estados:
            primeiro_estado = time.perf_counter() - inicio
        estados.append(estado)
    segundos_stream = time.perf_counter() - inicio
    fragmentos_pydantic = list(decorada.stream(entradas[0]))
    # R04: o modelo real repara saídas quebradas emitidas por um gerador duplo.
    laboratorio = ensaiar(modelo)
    for caso in laboratorio:
        obtido = (caso["resultado"] or {}).get("solicitacao", {})
        caso["dados_corretos"] = caso["camada_observada"] == "regra de domínio" or obtido == DADOS
    # R04: a mesma extração com with_structured_output, sem parser nem instruções de formato.
    estruturado = [Extracao.model_validate(resultado) for resultado in (
        PROMPT.partial(formato="") | modelo.with_structured_output(Extracao)).batch(entradas)]
    # R05/R06: o mesmo laboratório com a cadeia imperativa (@chain com try/except).
    laboratorio_imperativo = ensaiar(modelo, criar_chain_robusta)
    relatorio = {
        "fase": 1, "rubricas": ["R03", "R04", "R05", "R06"],
        "modo": "real remoto (OpenAI); solicitações sintéticas",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": nome, "temperature": 0,
        "modelo_de_prompt": {"classe": type(PROMPT).__name__,
                             "variaveis": sorted(PROMPT.input_variables),
                             "mensagens": [type(m).__name__ for m in PROMPT.messages]},
        "invoke_lcel": {"entrada": SOLICITACOES[0], "saida": um.model_dump()},
        "invoke_chain_decorada": {"entrada": SOLICITACOES[0], "saida": imperativa.model_dump()},
        "batch_lcel": [{"entrada": texto, "saida": resultado.model_dump()}
                       for texto, resultado in zip(SOLICITACOES, lote)],
        "laboratorio_saidas_quebradas": {
            "solicitacao": SOLICITACAO,
            "nota": "O gerador é um duplo que emite a saída quebrada; o reparador é o modelo real.",
            "casos": laboratorio},
        "with_structured_output": [
            {"entrada": texto, "saida": resultado.model_dump(),
             "igual_ao_parser": resultado.solicitacao == previo.solicitacao
             and resultado.intencao == previo.intencao}
            for texto, resultado, previo in zip(SOLICITACOES, estruturado, lote)],
        "tempos_invoke_e_batch": {
            "nota": "Uma única medição; depende da rede e do serviço. Não é um benchmark.",
            "tres_invoke_em_serie_segundos": round(segundos_serie, 2),
            "um_batch_de_tres_segundos": round(segundos_lote, 2),
            "mesmos_resultados": em_serie == lote},
        "stream": {
            "entrada": SOLICITACOES[0],
            "cadeia_json_parcial": {
                "estados_recebidos": len(estados),
                "segundos_ate_o_primeiro": round(primeiro_estado, 2),
                "segundos_totais": round(segundos_stream, 2),
                "amostra": [estados[i] for i in sorted({0, len(estados) // 3,
                                                        2 * len(estados) // 3, len(estados) - 1})]},
            "cadeia_pydantic_com_chain": {
                "fragmentos_recebidos": len(fragmentos_pydantic),
                "nota": "O parser Pydantic precisa do JSON completo: emite um único fragmento."}},
        "laboratorio_com_chain_imperativa": {
            "mesma_camada_que_a_declarativa": [c["camada_observada"] for c in laboratorio_imperativo]
            == [c["camada_observada"] for c in laboratorio],
            "dados_corretos": [c["camada_observada"] == "regra de domínio"
                               or (c["resultado"] or {}).get("solicitacao", {}) == DADOS
                               for c in laboratorio_imperativo]},
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for texto, resultado in zip(SOLICITACOES, lote):
        print(texto, "->", resultado.intencao,
              resultado.solicitacao.model_dump(exclude_none=True), "faltam", resultado.faltantes)
    for caso in laboratorio:
        print(f"  {caso['caso']:30} camada={caso['camada_observada']:17} "
              f"reparos={caso['reparos']} dados_corretos={caso['dados_corretos']}")
    print("with_structured_output igual ao parser:",
          [c["igual_ao_parser"] for c in relatorio["with_structured_output"]])
    print(f"invoke x3 em série: {segundos_serie:.2f}s | batch de 3: {segundos_lote:.2f}s | "
          f"mesmos resultados: {em_serie == lote}")
    print(f"stream JSON parcial: {len(estados)} estados, primeiro aos {primeiro_estado:.2f}s de "
          f"{segundos_stream:.2f}s | stream Pydantic: {len(fragmentos_pydantic)} fragmento")
    print("imperativa = declarativa no laboratório:",
          relatorio["laboratorio_com_chain_imperativa"]["mesma_camada_que_a_declarativa"],
          relatorio["laboratorio_com_chain_imperativa"]["dados_corretos"])
    print("salvo em", saida)


if __name__ == "__main__":
    main()
