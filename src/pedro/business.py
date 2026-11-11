"""Regras exatas em centavos: um frete, sem dividir pedidos e respeitando o pedido mínimo."""
from fractions import Fraction
from typing import Literal

from .contracts import Alternativa, Oferta, Solicitacao


def brl(centavos: int) -> str:
    return f"R$ {centavos // 100:,}".replace(",", ".") + f",{centavos % 100:02d}"


ROTULOS_MOTIVO = {"estoque": "estoque", "pedido_minimo": "pedido mínimo", "prazo": "prazo",
                  "orcamento": "orçamento"}


def descrever_motivos(alternativa: Alternativa) -> str:
    """Motivos de descarte em texto, com o dado que os explica quando ajuda."""
    partes = []
    for motivo in alternativa.motivos:
        if motivo == "pedido_minimo":
            partes.append(f"pedido mínimo ({alternativa.oferta.pedido_minimo} unidades)")
        else:
            partes.append(ROTULOS_MOTIVO[motivo])
    return ", ".join(partes)


def variacao_percentual(atual: int, referencia: int) -> int:
    """Variação de `atual` em relação a `referencia`, em pontos percentuais inteiros."""
    return round(Fraction(100 * (atual - referencia), referencia))


def descrever_preco(oferta: Oferta) -> str | None:
    """Situa o preço unitário vigente no seu histórico. Não muda a recomendação."""
    if not oferta.meses_historico or not oferta.preco_medio_centavos or not oferta.preco_anterior_centavos:
        return None
    atual = oferta.preco_unitario_centavos

    def mudanca(referencia: int) -> str:
        pontos = variacao_percentual(atual, referencia)
        return "igual" if pontos == 0 else f"{pontos:+d} %"

    texto = (f"{oferta.fornecedor_nome}: hoje {brl(atual)} por unidade; mês anterior "
             f"{brl(oferta.preco_anterior_centavos)} ({mudanca(oferta.preco_anterior_centavos)}); "
             f"média de {oferta.meses_historico} meses {brl(oferta.preco_medio_centavos)} "
             f"({mudanca(oferta.preco_medio_centavos)})")
    if atual == oferta.preco_minimo_centavos:
        texto += "; é o seu preço mais baixo do período"
    elif atual == oferta.preco_maximo_centavos:
        texto += "; é o seu preço mais alto do período"
    return texto + "."


def origem_preferida(preferencias: dict[str, str]) -> Literal["nacional", "internacional"] | None:
    """Traduz a preferência salva sobre fornecedores em um critério de comparação."""
    valor = " ".join(v for k, v in preferencias.items() if "fornecedor" in k.lower()).lower()
    # Radicais: em português o plural muda a terminação (nacional → nacionais, local → locais).
    if "internacion" in valor or "estrangeir" in valor or "importad" in valor:
        return "internacional"
    if "nacion" in valor or "loca" in valor or "brasil" in valor:
        return "nacional"
    return None


def comparar(solicitacao: Solicitacao, ofertas: list[Oferta]) -> list[Alternativa]:
    """Avalia cada oferta e as ordena: primeiro as que atendem; entre elas, as da origem
    que o usuário prefere; depois, por total, prazo e fornecedor."""
    if solicitacao.faltantes():
        raise ValueError("faltam: " + ", ".join(solicitacao.faltantes()))
    assert solicitacao.quantidade is not None
    resultado = []
    for oferta in ofertas:
        total = solicitacao.quantidade * oferta.preco_unitario_centavos + oferta.frete_centavos
        motivos: list[Literal["estoque", "pedido_minimo", "prazo", "orcamento"]] = []
        if oferta.estoque < solicitacao.quantidade:
            motivos.append("estoque")
        if solicitacao.quantidade < oferta.pedido_minimo:
            motivos.append("pedido_minimo")
        if solicitacao.prazo_max_dias is not None and oferta.prazo_dias > solicitacao.prazo_max_dias:
            motivos.append("prazo")
        if solicitacao.orcamento_centavos is not None and total > solicitacao.orcamento_centavos:
            motivos.append("orcamento")
        resultado.append(Alternativa(oferta=oferta, total_centavos=total,
                                     atende=not motivos, motivos=motivos))
    preferida = solicitacao.origem_preferida

    def fora_da_preferencia(alternativa: Alternativa) -> bool:
        return preferida is not None and alternativa.oferta.nacional != (preferida == "nacional")

    return sorted(resultado, key=lambda a: (not a.atende, fora_da_preferencia(a), a.total_centavos,
                                             a.oferta.prazo_dias, a.oferta.fornecedor_id))
