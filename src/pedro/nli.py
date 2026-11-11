"""Classificação NLI local de três classes com revisão fixada."""
from typing import Protocol

from .contracts import RespostaCompra

MODELO = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
REVISAO = "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"


class Classificador(Protocol):
    def classificar(self, premissa: str, hipotese: str) -> str: ...


class ModeloNLI:
    def __init__(self):
        from transformers import pipeline
        self._pipe = pipeline("text-classification", model=MODELO, tokenizer=MODELO,
                              revision=REVISAO, top_k=None)

    def classificar(self, premissa: str, hipotese: str) -> str:
        rotulos = self._pipe({"text": premissa, "text_pair": hipotese})
        if rotulos and isinstance(rotulos[0], list):
            rotulos = rotulos[0]
        vencedor = max(rotulos, key=lambda x: x["score"])["label"].lower()
        return vencedor if vencedor in {"entailment", "neutral", "contradiction"} else "neutral"


def verificar_nli(resposta: RespostaCompra, classificador: Classificador) -> bool:
    if resposta.estado == "politica":
        premissa = "\n".join(e.texto for e in resposta.evidencias if e.tipo == "politica")
        if not premissa or not resposta.mensagem:
            return False
        try:
            return classificador.classificar(premissa, resposta.mensagem) == "entailment"
        except Exception:
            return False
    if resposta.estado != "recomendacao":
        return True
    vencedora = next((a for a in resposta.alternativas
                      if a.oferta.fornecedor_id == resposta.fornecedor_id), None)
    if vencedora is None:
        return False
    fontes = [e.texto for e in resposta.evidencias if e.tipo == "catalogo"
              and e.dataset_id == resposta.dataset_id and e.fonte_id == vencedora.oferta.id]
    if not fontes:
        return False
    hipotese = (f"{vencedora.oferta.fornecedor_nome} tem estoque {vencedora.oferta.estoque} "
                f"e entrega em {vencedora.oferta.prazo_dias} dias")
    try:
        return classificador.classificar("\n".join(fontes), hipotese) == "entailment"
    except Exception:
        return False
