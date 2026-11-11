"""Congela 30 referências derivadas do catálogo, sem usar o comparador do agente.

A regra de referência inclui o pedido mínimo de cada oferta.
"""
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONTE = ROOT / "datasets/pecas_eletrodomesticos.sqlite3"
DESTINO = ROOT / "evals/casos_derivados.json"


def brl(centavos):
    return f"R$ {centavos // 100:,}".replace(",", ".") + f",{centavos % 100:02d}"


casos = []
candidatos = [f"PEC-{categoria:02d}-0001" for categoria in range(1, 12)]
candidatos += [f"PEC-{categoria:02d}-0002" for categoria in range(1, 12)]
bloqueados_por_minimo = []
with sqlite3.connect(FONTE) as db:
    for produto_id in candidatos:
        linhas = db.execute(
            "SELECT o.id,o.supplier_id,o.estimated_brl_cents,o.shipping_brl_cents,"
            "o.stock_qty,o.lead_days,o.min_order_qty FROM offers o WHERE o.part_id=?",
            (produto_id,)).fetchall()
        # Regra de referência, escrita aqui à parte: estoque suficiente, pedido mínimo atendido,
        # prazo e orçamento dentro dos limites; vence o menor total.
        validas = [(2 * preco + frete, prazo, fornecedor, oferta)
                   for oferta, fornecedor, preco, frete, estoque, prazo, minimo in linhas
                   if estoque >= 2 and minimo <= 2 and prazo <= 60 and 2 * preco + frete <= 10_000_000]
        if not validas:
            com_estoque = any(estoque >= 2 and prazo <= 60 for *_, estoque, prazo, _ in linhas)
            if com_estoque:
                bloqueados_por_minimo.append(produto_id)
            continue
        if sum(c["grupo"] == "recomendacao" for c in casos) == 14:
            continue
        total, _, fornecedor, oferta = min(validas)
        casos.append({
            "id": f"rec-{len(casos)+1:02d}", "grupo": "recomendacao",
            "pergunta": (f"Compare 2 unidades de {produto_id}; orçamento R$ 100000 "
                         "e prazo máximo 60 dias."),
            "esperado": {"estado": "recomendacao", "vencedor": fornecedor,
                         "total_centavos": total, "total_brl": brl(total),
                         "fonte_vencedora": oferta,
                         "ferramentas": ["consultar_catalogo", "comparar_ofertas"]},
        })
if sum(c["grupo"] == "recomendacao" for c in casos) != 14 or len(bloqueados_por_minimo) < 3:
    raise RuntimeError("não há referências suficientes")

# Sem oferta: dois por quantidade impossível e três porque nenhum fornecedor aceita um pedido de 2.
for produto_id, quantidade in [(candidatos[0], 1000), (candidatos[1], 1000),
                               *[(produto_id, 2) for produto_id in bloqueados_por_minimo[:3]]]:
    casos.append({
        "id": f"sem-{len(casos)+1:02d}", "grupo": "sem_oferta",
        "pergunta": (f"Compare {quantidade} unidades de {produto_id}; orçamento R$ 100000 "
                     "e prazo máximo 60 dias."),
        "esperado": {"estado": "sem_oferta", "contem": "Nenhuma oferta",
                     "ferramentas": ["consultar_catalogo", "comparar_ofertas"]},
    })

for pergunta in [
    "Quero PEC-01-0001.",
    "Compare PEC-02-0001 com orçamento R$ 100000 e prazo 60 dias.",
    "Preciso de 2 peças de reposição com orçamento R$ 100000 e prazo 60 dias. Qual peça?",
    "Quero comparar ofertas, mas ainda não sei a peça nem a quantidade.",
]:
    casos.append({"id": f"esc-{len(casos)+1:02d}", "grupo": "esclarecimento",
                  "pergunta": pergunta,
                  "esperado": {"estado": "esclarecimento", "contem": "?",
                               "ferramentas": []}})

for pergunta, contem in [
    ("lista peças", "PEC-01-0001"),
    ("lista peças página 2", "PEC-01-0021"),
    ("ficha PEC-01-0001", "PEC-01-0001"),
]:
    casos.append({"id": f"cat-{len(casos)+1:02d}", "grupo": "catalogo",
                  "pergunta": pergunta,
                  "esperado": {"estado": "catalogo", "contem": contem, "ferramentas": []}})

for pergunta in ["Consulte o CEP 01001000", "A qual cidade corresponde 01001000?"]:
    casos.append({"id": f"cep-{len(casos)+1:02d}", "grupo": "cep",
                  "pergunta": pergunta,
                  "esperado": {"estado": "cep", "contem": "São Paulo/SP",
                               "ferramentas": ["consultar_cep"]}})

for pergunta in ["O que diz a política de devoluções?", "Existe política de trocas?"]:
    casos.append({"id": f"pol-{len(casos)+1:02d}", "grupo": "politica_sem_indice",
                  "pergunta": pergunta,
                  "esperado": {"estado": "sem_evidencia", "contem": "Não posso confirmar",
                               "ferramentas": ["consultar_politicas"]}})

assert len(casos) == 30
DESTINO.write_text(json.dumps({
    "tipo": "derivados_sinteticos_nao_oficiais",
    "fonte_sha256": hashlib.sha256(FONTE.read_bytes()).hexdigest(),
    "casos": casos,
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(DESTINO, len(casos))
