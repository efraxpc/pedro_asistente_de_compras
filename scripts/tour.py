"""Tour das rubricas: executa uma parada por vez e mostra o que acontece.

Uso: uv run python scripts/tour.py 1   (precisa de OPENAI_API_KEY)
"""
import sys

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from pedro.chains import PROMPT, criar_lcel

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


PARADAS = {"1": parada_1}

if __name__ == "__main__":
    escolha = sys.argv[1] if len(sys.argv) > 1 else "1"
    if escolha not in PARADAS:
        sys.exit(f"Paradas disponíveis: {', '.join(PARADAS)}")
    PARADAS[escolha]()
