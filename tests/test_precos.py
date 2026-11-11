import json

import pytest
from langchain_core.runnables import RunnableLambda

from pedro.catalog import criar_cenario
from pedro.contracts import Oferta, Solicitacao
from pedro.precos import (aconselhar, aviso_de_preco, criar_conselheiro, fatos_de_preco,
                          sinal_preco, verificar_conselho)
from pedro.verification import resposta_local


def _oferta(atual: int, media: int, **extra) -> Oferta:
    return Oferta(dataset_id="d", id="o", produto_id="PEC-01-0001", fornecedor_id="BR-01",
                  fornecedor_nome="Teste", preco_unitario_centavos=atual, frete_centavos=0,
                  estoque=9, prazo_dias=1, meses_historico=5, preco_medio_centavos=media,
                  preco_anterior_centavos=media, preco_minimo_centavos=min(atual, media) - 1,
                  preco_maximo_centavos=max(atual, media) + 1, **extra)


@pytest.mark.parametrize("atual, nivel", [
    (125, "muito acima"), (120, "muito acima"), (119, "acima"), (110, "acima"),
    (109, "em linha"), (100, "em linha"), (91, "em linha"), (90, "abaixo"),
    (81, "abaixo"), (80, "muito abaixo"),
])
def test_o_sinal_classifica_o_preco_com_limiares_fixos(atual, nivel):
    sinal = sinal_preco(_oferta(atual, 100))
    assert sinal.nivel == nivel and sinal.frente_a_media == atual - 100


def test_sem_historico_nao_ha_sinal():
    oferta = _oferta(100, 100).model_copy(update={"preco_medio_centavos": None})
    assert sinal_preco(oferta) is None


@pytest.fixture
def cara(tmp_path):
    """PEC-02-0189, 5 unidades: vence CentroPeças com o preço 11 % acima da sua média."""
    cenario = criar_cenario(tmp_path / "catalogos")
    return resposta_local(cenario, Solicitacao(produto_id="PEC-02-0189", quantidade=5))


def test_o_aviso_aponta_um_preco_alto_e_uma_alternativa_quase_igual(cara, tmp_path):
    aviso = aviso_de_preco(cara)
    assert aviso == ("O preço de CentroPeças está 11 % acima da sua média de 5 meses. "
                     "Atlantic Repair Parts custa R$ 12,89 a mais (1 %) e o seu preço está 10 % "
                     "abaixo da sua média.")
    assert cara.fornecedor_id == "BR-06"  # o aviso não muda o vencedor
    fatos = fatos_de_preco(cara)
    assert fatos[0].startswith("A oferta recomendada é a de CentroPeças")
    assert any("Atlantic Repair Parts também atende" in f for f in fatos)
    # Se o preço do vencedor está em linha com a sua média, não se avisa de nada.
    normal = resposta_local(criar_cenario(tmp_path / "outro"), Solicitacao(produto_id="PEC-01-0001", quantidade=5))
    assert aviso_de_preco(normal) is None
    assert aconselhar(normal, None, None) == {"texto": None, "fonte": "nada a avisar"}


def _conselheiro(texto: str):
    return criar_conselheiro(RunnableLambda(lambda _: json.dumps({"conselho": texto})))


class NLI:
    def __init__(self, rotulo):
        self.rotulo, self.vistos = rotulo, []

    def classificar(self, premissa, hipotese):
        self.vistos.append((premissa, hipotese))
        return self.rotulo


BOM = ("CentroPeças está 11 % acima da sua média de 5 meses; Atlantic Repair Parts custa "
       "só 1 % a mais e está 10 % abaixo da sua média.")


def test_um_conselho_respaldado_substitui_o_aviso_fixo(cara):
    nli = NLI("entailment")
    resultado = aconselhar(cara, _conselheiro(BOM), nli)
    assert resultado["fonte"] == "conselho verificado" and resultado["texto"] == BOM
    premissa, hipotese = nli.vistos[0]
    assert hipotese == BOM and "11 % acima" in premissa


@pytest.mark.parametrize("conselho, rotulo, motivo", [
    ("CentroPeças está 30 % acima da sua média; melhor Atlantic Repair Parts.", "entailment", "números"),
    ("Há uma opção melhor que custa quase o mesmo e convém olhá-la.", "entailment", "nenhum fornecedor"),
    ("CentroPeças está 11 % acima da sua média e o seu preço vai baixar em breve.", "entailment", "prevê"),
    (BOM, "neutral", "NLI: neutral"),
    (BOM, "contradiction", "NLI: contradiction"),
])
def test_um_conselho_sem_respaldo_e_descartado_e_fica_o_aviso_fixo(cara, conselho, rotulo, motivo):
    resultado = aconselhar(cara, _conselheiro(conselho), NLI(rotulo))
    assert resultado["fonte"] == "aviso fixo" and resultado["texto"] == aviso_de_preco(cara)
    assert resultado["conselho_rejeitado"] == conselho
    assert any(motivo in erro for erro in resultado["erros"])


def test_se_o_modelo_falha_ou_nao_ha_nli_fica_o_aviso_fixo(cara):
    quebrado = criar_conselheiro(RunnableLambda(lambda _: "não é JSON"))
    assert aconselhar(cara, quebrado, NLI("entailment"))["fonte"] == "aviso fixo"
    assert aconselhar(cara, _conselheiro(BOM), None)["erros"] == ["sem classificador NLI"]
    assert aconselhar(cara, None, None)["fonte"] == "aviso fixo"
    assert verificar_conselho(BOM, fatos_de_preco(cara), ["CentroPeças"], NLI("entailment")) == []
