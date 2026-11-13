"""Resposta direta a perguntas sobre a comparação: fatos, resumo fixo, porta e fluxo."""
import pytest

from pedro.agent import criar_fluxo, partes_de
from pedro.catalog import criar_cenario
from pedro.contracts import Solicitacao
from pedro.dialogue import EstadoCompra, pergunta_sobre_comparacao
from pedro.memory import nova_sessao
from pedro.resposta_direta import (fatos_da_comparacao, responder, resumo_fixo,
                                   verificar_resposta_direta)
from pedro.verification import resposta_local


class NLI:
    def __init__(self, rotulo="entailment"):
        self.rotulo = rotulo

    def classificar(self, premissa, hipotese):
        return self.rotulo


class Respondedor:
    """Duplo de teste do modelo: devolve sempre a mesma frase."""
    def __init__(self, texto):
        self.texto = texto

    def invoke(self, dado):
        from pedro.resposta_direta import RespostaDireta
        return RespostaDireta(resposta=self.texto)


@pytest.fixture
def comparacao(tmp_path):
    cenario = criar_cenario(tmp_path / "catalogos")
    return resposta_local(cenario, Solicitacao(produto_id="PEC-01-0001", quantidade=5, prazo_max_dias=7))


def test_os_fatos_e_o_resumo_fixo_saem_da_comparacao(comparacao):
    fatos = " ".join(fatos_da_comparacao(comparacao))
    assert "A oferta recomendada é a de CentroPeças." in fatos
    assert "A oferta de menor total entre todas é a de Litoral Parts." in fatos
    assert "R$ 7.279,83" in fatos and "R$ 1.930,40" in fatos and "prazo máximo de 7 dias" in fatos
    resumo = resumo_fixo(comparacao)
    assert "A mais barata que atende às suas restrições é a de CentroPeças, por R$ 7.279,83" in resumo
    assert "Litoral Parts, por R$ 1.930,40, mas foi descartada porque não tem estoque suficiente" in resumo


def test_a_frase_do_modelo_so_e_publicada_se_passar_na_porta(comparacao):
    boa = "A mais barata que atende é a de CentroPeças, por R$ 7.279,83."
    publicada = responder(comparacao, "a mais barata?", Respondedor(boa), NLI())
    assert publicada == {"texto": boa, "fonte": "resposta verificada"}

    inventada = responder(comparacao, "a mais barata?",
                          Respondedor("A mais barata é a de CentroPeças, por R$ 6.000,00."), NLI())
    assert inventada["fonte"] == "resumo fixo" and inventada["texto"] == resumo_fixo(comparacao)
    assert inventada["erros"] == ["a resposta contém números que não estão nos fatos"]

    sem_apoio = responder(comparacao, "a mais barata?", Respondedor(boa), NLI("neutral"))
    assert sem_apoio["fonte"] == "resumo fixo" and sem_apoio["erros"] == ["NLI: neutral"]

    assert responder(comparacao, "a mais barata?", None, None)["fonte"] == "resumo fixo"
    fatos = fatos_da_comparacao(comparacao)
    assert verificar_resposta_direta("É a mais barata.", fatos, ["CentroPeças"], NLI()) == [
        "a resposta não nomeia nenhum fornecedor comparado"]


@pytest.mark.parametrize("mensagem, esperado", [
    ("a mais barata?", True),
    ("qual chega mais rápido?", True),
    ("por que não a Litoral Parts?", True),
    ("A que cidade corresponde o CEP 01001000?", False),
    ("A garantia cobre a instalação?", False),
    ("Posso receber em várias caixas?", False),
    ("Obrigado, isso é tudo", False),
    ("Quais categorias de peças existem?", False),
    ("Qual é a peça de maior potência?", False),
    ("Olá, tudo bem?", False),
])
def test_reconhece_perguntas_sobre_a_comparacao_em_andamento(mensagem, esperado):
    em_andamento = EstadoCompra(solicitacao=Solicitacao(produto_id="PEC-01-0001", quantidade=5))
    fornecedores = ("CentroPeças", "Litoral Parts", "Atlantic Repair Parts")
    assert pergunta_sobre_comparacao(em_andamento, mensagem, fornecedores) is esperado
    assert pergunta_sobre_comparacao(None, mensagem, fornecedores) is False
    incompleta = EstadoCompra(solicitacao=Solicitacao(produto_id="PEC-01-0001"), esperando="quantidade")
    assert pergunta_sobre_comparacao(incompleta, mensagem) is False


def test_no_fluxo_sem_modelo_a_pergunta_recebe_o_resumo_e_a_mesma_comparacao(tmp_path):
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    fluxo = criar_fluxo(cenario, memoria)
    config = {"configurable": {"user_id": "ana", "session_id": sessao}}

    primeira = fluxo.invoke({"input": "Compare 5 unidades de PEC-01-0001 com prazo de 7 dias"}, config=config)
    assert partes_de(primeira)[0]["direta"] is None  # não foi uma pergunta

    segunda = fluxo.invoke({"input": "a mais barata?"}, config=config)
    parte = partes_de(segunda)[0]
    assert parte["direta"]["fonte"] == "resumo fixo"
    assert segunda.content.startswith("A mais barata que atende às suas restrições é a de CentroPeças")
    assert parte["comparacao"]["total_centavos"] == 5 * 143892 + 8523
    assert parte["comparacao"]["solicitacao"]["prazo_max_dias"] == 7  # a solicitação não muda


# --- Resposta a perguntas sobre uma política já recuperada (rota de entrega parcial). ---

POLITICA = ("Uma entrega parcial só pode ser descrita se há um acordo simulado explícito que identifica "
            "as unidades, o fornecedor e os prazos de cada envio. Se não existe esse acordo, o assistente "
            "deve indicar que a oferta não cobre a quantidade pedida.")


class RespondedorPolitica:
    """Duplo de teste do modelo: devolve sempre a mesma decisão e a mesma frase."""
    def __init__(self, responde, texto):
        self.responde, self.texto = responde, texto

    def invoke(self, dado):
        from pedro.resposta_direta import RespostaPolitica
        return RespostaPolitica(responde_ao_perguntado=self.responde, resposta=self.texto)


def test_a_frase_sobre_a_politica_so_e_publicada_se_passar_na_porta():
    from pedro.resposta_direta import responder_politica

    frase = "Só se há um acordo simulado explícito que identifica as unidades."
    publicada = responder_politica("Posso receber em várias caixas?", POLITICA,
                                   RespondedorPolitica(True, frase), NLI())
    assert publicada == {"texto": frase, "responde": True, "fonte": "resposta verificada"}

    inventada = responder_politica("Em quantos dias?", POLITICA,
                                   RespondedorPolitica(False, "Chega em 3 dias em caixas separadas."), NLI())
    assert inventada["texto"] is None and inventada["fonte"] == "regra literal"
    assert inventada["responde"] is False  # a decisão do modelo é conservada
    assert inventada["erros"] == ["a resposta contém números que não estão na política"]

    sem_apoio = responder_politica("Posso?", POLITICA, RespondedorPolitica(True, frase), NLI("neutral"))
    assert sem_apoio["texto"] is None and sem_apoio["erros"] == ["NLI: neutral"]

    assert responder_politica("Posso?", POLITICA, None, None) == {
        "texto": None, "responde": None, "fonte": "regra literal"}


def test_o_resumo_da_recuperacao_nao_afirma_uma_correcao_que_nao_houve():
    from pedro.agent import resumo_recuperacao_t24

    corrigida = {"correcao_observada": True, "fonte_esperada": "FIC-ENT-01-S05-C01", "k": 4,
                 "posicao_antes": None, "posicao_depois": 1}
    assert "fora do top-4" in resumo_recuperacao_t24(corrigida)
    sem_falha = {**corrigida, "correcao_observada": False, "posicao_antes": 2}
    texto = resumo_recuperacao_t24(sem_falha)
    assert "já trazia" in texto and "posição 2" in texto and "fora do top" not in texto
    assert resumo_recuperacao_t24(None) == ""
