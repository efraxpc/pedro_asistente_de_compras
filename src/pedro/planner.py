"""Planejador de turno: divide uma mensagem com várias intenções em pedidos independentes.

Cada pedido é resolvido depois com o fluxo normal de uma única intenção, de modo que cada
parte passa pela sua própria verificação.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

# Sinais baratos de cada intenção. Servem para decidir se vale a pena chamar o planejador.
SINAIS = {
    "compra": r"\bPEC-[0-9]{2}-[0-9]{4}\b|\b(compara|compare|comparar|cota|cote|cotar|preciso|quero|"
              r"ofertas?|pre[cç]o)\b",
    "politica": r"\b(pol[ií]ticas?|garantia|devolu[cç][aã]o|devolver|reembolso|compatibilidade|"
                r"instalar|instala[cç][aã]o|v[aá]rias\s+caixas|envio\s+parcial|entrega\s+parcial)\b",
    "cep": r"\bcep\b|\b\d{5}-?\d{3}\b",
    "preferencia": r"\b(prefiro|lembre-se|lembr[ae]\s+disso|lembr[ae]\s+que|"
                   r"(?:guarde|guarda|salve|salva)\s+(?:a\s+)?minha\s+prefer[eê]ncia)\b",
}
MAX_PEDIDOS = 4


class Pedido(BaseModel):
    tipo: Literal["compra", "politica", "cep", "preferencia"]
    pedido: str = Field(min_length=3, description="Pedido completo e autônomo, com os seus dados")


class PlanoTurno(BaseModel):
    """Plano observável de um turno: um pedido por intenção, na ordem da mensagem."""
    pedidos: list[Pedido] = Field(min_length=1, max_length=MAX_PEDIDOS)


def intencoes_detectadas(texto: str) -> set[str]:
    return {nome for nome, padrao in SINAIS.items() if re.search(padrao, texto, re.I)}


def _dados(texto: str) -> set[str]:
    """Identificadores e números de um texto, para comprovar que o plano não acrescenta nenhum."""
    return set(re.findall(r"PEC-[0-9]{2}-[0-9]{4}|\d+(?:[.,]\d+)*", texto.upper()))


def validar_plano(plano: PlanoTurno, original: str) -> list[Pedido]:
    """Aceita o plano somente se cada pedido for coerente com a mensagem do usuário.

    Regras: um tipo não se repete, cada pedido mostra o sinal do seu tipo e não contém
    nenhum identificador nem número que o usuário não tenha escrito.
    """
    tipos = [p.tipo for p in plano.pedidos]
    if len(set(tipos)) != len(tipos):
        raise ValueError("o plano repete um tipo de pedido")
    permitidos = _dados(original)
    for pedido in plano.pedidos:
        if not re.search(SINAIS[pedido.tipo], pedido.pedido, re.I):
            raise ValueError(f"o pedido de {pedido.tipo} não parece ser desse tipo")
        if _dados(pedido.pedido) - permitidos:
            raise ValueError("o plano acrescenta dados que o usuário não escreveu")
    return plano.pedidos


def criar_planejador(modelo):
    """Cadeia que propõe um `PlanoTurno`. Não executa nada."""
    from langchain_core.output_parsers import PydanticOutputParser

    from .prompts import MODELO_PLANO

    parser = PydanticOutputParser(pydantic_object=PlanoTurno)
    return MODELO_PLANO.partial(formato=parser.get_format_instructions()) | modelo | parser


def planejar_turno(mensagem: str, modelo) -> list[Pedido] | None:
    """Devolve os pedidos de uma mensagem mista, ou None se ela deve ser tratada como uma só.

    O modelo só é consultado quando a mensagem mostra sinais de duas ou mais intenções; um
    plano inválido, ilegível ou de um único pedido equivale a não planejar.
    """
    if modelo is None or len(intencoes_detectadas(mensagem)) < 2:
        return None
    try:
        pedidos = validar_plano(criar_planejador(modelo).invoke({"mensagem": mensagem}), mensagem)
    except Exception:
        return None
    return pedidos if len(pedidos) > 1 else None
