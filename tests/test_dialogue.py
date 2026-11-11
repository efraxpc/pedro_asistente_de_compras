import pytest

from pedro.agent import criar_fluxo
from pedro.catalog import criar_cenario
from pedro.dialogue import EstadoCompra, interpretar_compra
from pedro.memory import ler_rascunho, nova_sessao


@pytest.fixture
def contexto(tmp_path):
    cenario = criar_cenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sessao = nova_sessao(memoria, "ana", cenario.dataset_id)
    fluxo = criar_fluxo(cenario, memoria)

    def perguntar(texto, session_id=sessao, user_id="ana"):
        return str(fluxo.invoke({"input": texto}, config={"configurable": {
            "user_id": user_id, "session_id": session_id}}).content)

    return cenario, memoria, sessao, perguntar


def test_pede_so_quantidade_e_compara_sem_limites(contexto):
    cenario, memoria, sessao, perguntar = contexto
    pergunta = perguntar("Compare PEC-01-0001")
    assert "De quantas unidades" in pergunta
    assert "orcamento_centavos" not in pergunta
    resposta = perguntar("2, por favor")
    assert "Fontes:" in resposta
    assert "PEC-01-0001" in ler_rascunho(memoria, "ana", sessao)["solicitacao"]["produto_id"]
    solicitacao = EstadoCompra.model_validate(ler_rascunho(memoria, "ana", sessao)).solicitacao
    assert solicitacao.quantidade == 2
    assert solicitacao.orcamento_centavos is None
    assert solicitacao.prazo_max_dias is None
    assert resposta != perguntar("agora 3 unidades")
    assert ler_rascunho(memoria, "ana", sessao)["solicitacao"]["quantidade"] == 3
    perguntar("muda a quantidade para dois")
    assert ler_rascunho(memoria, "ana", sessao)["solicitacao"]["quantidade"] == 2


def test_correcao_conserva_filtros_explicitos_e_permite_remove_los(contexto):
    _, memoria, sessao, perguntar = contexto
    resposta = perguntar("Compare 2 unidades de PEC-01-0001 com orçamento R$ 1.000,00 e prazo 7 dias")
    assert "Fontes:" in resposta
    perguntar("Agora 3 unidades")
    solicitacao = EstadoCompra.model_validate(ler_rascunho(memoria, "ana", sessao)).solicitacao
    assert (solicitacao.quantidade, solicitacao.orcamento_centavos, solicitacao.prazo_max_dias) == (3, 100000, 7)
    perguntar("Sem orçamento e sem prazo")
    solicitacao = EstadoCompra.model_validate(ler_rascunho(memoria, "ana", sessao)).solicitacao
    assert solicitacao.orcamento_centavos is None
    assert solicitacao.prazo_max_dias is None


def test_rascunho_isolado_por_sessao_e_usuario(contexto):
    cenario, memoria, sessao, perguntar = contexto
    perguntar("Compare PEC-01-0001")
    outra = nova_sessao(memoria, "ana", cenario.dataset_id)
    assert "De qual peça" in perguntar("Compare", outra)
    assert ler_rascunho(memoria, "ana", outra)["solicitacao"]["produto_id"] is None
    with pytest.raises(ValueError, match="sessão alheia"):
        ler_rascunho(memoria, "outra", sessao)


def test_cep_nao_reutiliza_rascunho_de_compra(contexto):
    cenario, memoria, sessao, perguntar = contexto
    perguntar("Compare PEC-01-0001")
    previo = EstadoCompra.model_validate(ler_rascunho(memoria, "ana", sessao))
    assert interpretar_compra(cenario, previo, "Consulte o CEP 01001000") is None


@pytest.mark.parametrize("mensagem, quantidade", [
    ("Agora que sejam 3 e mantenha o prazo", 3),
    ("Melhor 4", 4),
    ("muda para 5", 5),
    ("que sejam seis", 6),
    ("agora meia dúzia", 6),
])
def test_mudanca_de_quantidade_dita_de_passagem_conserva_o_prazo(contexto, mensagem, quantidade):
    cenario, _, _, _ = contexto
    previo, _ = interpretar_compra(cenario, None, "Preciso de 2 unidades de PEC-01-0001 com prazo de 7 dias")
    estado, esclarecimento = interpretar_compra(cenario, previo, mensagem)
    assert esclarecimento is None
    assert (estado.solicitacao.quantidade, estado.solicitacao.prazo_max_dias) == (quantidade, 7)


def test_mudar_o_prazo_nao_se_confunde_com_a_quantidade(contexto):
    cenario, _, _, _ = contexto
    previo, _ = interpretar_compra(cenario, None, "Preciso de 2 unidades de PEC-01-0001")
    estado, _ = interpretar_compra(cenario, previo, "melhor 10 dias de prazo")
    assert (estado.solicitacao.quantidade, estado.solicitacao.prazo_max_dias) == (2, 10)


@pytest.mark.parametrize("mensagem", [
    "Como se verifica a compatibilidade elétrica antes de instalar uma peça?",
    "O que a garantia de uma peça cobre?",
    "Prefiro fornecedores nacionais, lembre-se disso",
    "A que cidade corresponde o CEP 01001000?",
])
def test_perguntas_que_nao_sao_compra_nao_tocam_o_rascunho(contexto, mensagem):
    cenario, _, _, _ = contexto
    previo, _ = interpretar_compra(cenario, None, "Preciso de 2 unidades de PEC-01-0001")
    assert interpretar_compra(cenario, previo, mensagem) is None


def test_preferencia_so_e_confirmada_se_a_ferramenta_a_salvou(tmp_path):
    from pedro.contracts import RespostaCompra, Solicitacao
    from pedro.verification import ancorar_preferencia, verificar

    cenario = criar_cenario(tmp_path / "catalogos")
    resposta = RespostaCompra(estado="preferencia", dataset_id=cenario.dataset_id,
                              solicitacao=Solicitacao(), mensagem="Feito, e além disso recomendo o BR-06.")
    salva = ("salvar_preferencia", {"estado": "ok", "chave": "fornecedor", "valor": "nacionais"})
    assert verificar(resposta, cenario, observacoes=[]) == ["preferência não salva"]
    assert ancorar_preferencia(resposta, [salva])["estado"] == "ancorada"
    assert resposta.mensagem == "Salvei a sua preferência: fornecedor = nacionais."
    assert verificar(resposta, cenario, observacoes=[salva]) == []
    rejeitada = ("salvar_preferencia", {"estado": "invalido", "erro": "sem pedido explícito"})
    assert verificar(resposta, cenario, observacoes=[rejeitada]) == ["preferência não salva"]


def _interprete(**mudanca):
    import json

    from langchain_core.runnables import RunnableLambda

    from pedro.dialogue import criar_interprete

    vistos = []

    def modelo(prompt):
        vistos.append(prompt.to_messages()[-1].content)
        return json.dumps(mudanca)

    return criar_interprete(RunnableLambda(modelo)), vistos


def test_o_modelo_entende_uma_mudanca_que_as_regras_nao_veem(contexto):
    from pedro.dialogue import interpretar_turno

    cenario, _, _, _ = contexto
    previo, _ = interpretar_compra(cenario, None, "Preciso de 2 unidades de PEC-01-0001 com prazo de 7 dias")
    assert interpretar_compra(cenario, previo, "Suba para meia dúzia") is None
    interprete, vistos = _interprete(e_compra=True, quantidade=6)
    (estado, esclarecimento), relatorio = interpretar_turno(cenario, previo, "Suba para meia dúzia", interprete)
    assert esclarecimento is None and relatorio["fonte"] == "modelo"
    assert (estado.solicitacao.produto_id, estado.solicitacao.quantidade,
            estado.solicitacao.prazo_max_dias) == ("PEC-01-0001", 6, 7)
    assert '"quantidade":2' in vistos[0] and "Suba para meia dúzia" in vistos[0]


def test_o_modelo_remove_um_limite_e_conserva_o_resto(contexto):
    from pedro.dialogue import interpretar_turno

    cenario, _, _, _ = contexto
    previo, _ = interpretar_compra(cenario, None, "Preciso de 2 unidades de PEC-01-0001 com prazo de 7 dias")
    interprete, _ = _interprete(e_compra=True, orcamento_centavos=500000, remover=["prazo"])
    (estado, _), _ = interpretar_turno(cenario, previo, "Esqueça o prazo; teto de 5 mil", interprete)
    assert (estado.solicitacao.quantidade, estado.solicitacao.orcamento_centavos,
            estado.solicitacao.prazo_max_dias) == (2, 500000, None)


def test_se_o_modelo_diz_que_nao_e_compra_o_rascunho_nao_e_tocado(contexto):
    from pedro.dialogue import interpretar_turno

    cenario, _, _, _ = contexto
    previo, _ = interpretar_compra(cenario, None, "Preciso de 2 unidades de PEC-01-0001")
    interprete, _ = _interprete(e_compra=False)
    resultado, relatorio = interpretar_turno(cenario, previo, "Obrigado, isso é tudo", interprete)
    assert resultado is None and relatorio["modelo"] == {"e_compra": False, "remover": []}


def test_sem_modelo_ou_com_saida_ilegivel_valem_as_regras(contexto):
    from langchain_core.runnables import RunnableLambda

    from pedro.dialogue import criar_interprete, interpretar_turno

    cenario, _, _, _ = contexto
    previo, _ = interpretar_compra(cenario, None, "Preciso de 2 unidades de PEC-01-0001")
    regras = interpretar_compra(cenario, previo, "Agora 3 unidades")
    assert interpretar_turno(cenario, previo, "Agora 3 unidades", None) == (regras, {"fonte": "regras"})
    quebrado = criar_interprete(RunnableLambda(lambda _: "não é JSON"))
    resultado, relatorio = interpretar_turno(cenario, previo, "Agora 3 unidades", quebrado)
    assert resultado == regras and relatorio["fonte"] == "regras"


def test_a_peca_e_resolvida_pelas_regras_mesmo_havendo_modelo(contexto):
    from pedro.dialogue import interpretar_turno

    cenario, _, _, _ = contexto
    interprete, _ = _interprete(e_compra=True, quantidade=2)
    (estado, esclarecimento), _ = interpretar_turno(cenario, None, "Compare 2 unidades de PEC-99-9999", interprete)
    assert estado.esperando == "produto" and "Não encontrei PEC-99-9999" in esclarecimento
    sem_peca, relatorio = interpretar_turno(cenario, None, "Olá", interprete)
    assert sem_peca is None and relatorio == {"fonte": "regras"}


def test_a_preferencia_salva_muda_a_recomendacao_do_chat(contexto):
    from pedro.memory import salvar_preferencia

    _, memoria, _, perguntar = contexto
    antes = perguntar("Preciso de 5 unidades de PEC-01-0001")
    assert antes.startswith("CentroPeças") and "preferência" not in antes
    salvar_preferencia(memoria, "ana", "fornecedor", "internacionais", explicita=True)
    depois = perguntar("Compare de novo 5 unidades de PEC-01-0001")
    assert depois.startswith("Atlantic Repair Parts")
    assert "Foi aplicada a sua preferência por fornecedores internacionais." in depois
    assert "Sem ela, a mais barata seria CentroPeças" in depois
