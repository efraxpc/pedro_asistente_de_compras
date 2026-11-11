"""Tour das rubricas: executa uma parada por vez e mostra o que acontece.

Uso: uv run python scripts/tour.py 1   (precisa de OPENAI_API_KEY)
"""
import sys
import time

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from pedro.chains import PROMPT, criar_chain, criar_lcel, criar_lcel_parcial

load_dotenv()


def parada_1() -> None:
    """R03 e R04: modelo de prompt -> LLM -> parser."""
    texto = "Compare 5 unidades de PEC-01-0001 com prazo de 7 dias"
    print("1) O que o usuário escreveu:\n  ", texto)
    print("\n2) Variáveis do modelo de prompt (R03):", sorted(PROMPT.input_variables))
    resultado = criar_lcel(ChatOpenAI(model="gpt-4.1-mini", temperature=0)).invoke({"texto": texto})
    print("\n3) O que o parser devolve (R04), já como objeto Python:")
    print("   intenção  :", resultado.intencao)
    print("   peça      :", resultado.solicitacao.produto_id)
    print("   quantidade:", resultado.solicitacao.quantidade)
    print("   prazo     :", resultado.solicitacao.prazo_max_dias, "dias")
    print("   faltantes :", resultado.faltantes)


def parada_2() -> None:
    """R05 e R06: invoke, batch, stream e a mesma cadeia escrita com @chain."""
    modelo = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
    pedidos = [{"texto": "Compare 5 unidades de PEC-01-0001 com prazo de 7 dias"},
               {"texto": "Quero 2 unidades de PEC-02-0189"},
               {"texto": "Preciso de 3 unidades de PEC-11-0001 com orçamento de R$ 5000"}]
    cadeia = criar_lcel(modelo)

    inicio = time.perf_counter()
    um_a_um = [cadeia.invoke(pedido) for pedido in pedidos]
    print(f"invoke: 3 pedidos, um de cada vez  -> {time.perf_counter() - inicio:.1f} s")

    inicio = time.perf_counter()
    juntos = cadeia.batch(pedidos)
    print(f"batch : os mesmos 3 em paralelo    -> {time.perf_counter() - inicio:.1f} s")
    print("        mesmos resultados?", um_a_um == juntos)

    print("stream: o JSON vai chegando aos pedaços")
    for numero, pedaco in enumerate(criar_lcel_parcial(modelo).stream(pedidos[0])):
        if numero % 5 == 0:
            print("       ", pedaco)

    com_decorador = criar_chain(modelo).invoke(pedidos[0])
    print("@chain: mesma resposta que a cadeia com | ?", com_decorador == um_a_um[0])


PARADAS = {"1": parada_1, "2": parada_2}

if __name__ == "__main__":
    escolha = sys.argv[1] if len(sys.argv) > 1 else "1"
    if escolha not in PARADAS:
        sys.exit(f"Paradas disponíveis: {', '.join(PARADAS)}")
    PARADAS[escolha]()
