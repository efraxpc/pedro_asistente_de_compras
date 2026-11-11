import json

import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import RunnableLambda

from pedro.chains import (criar_chain, criar_chain_robusta, criar_lcel, criar_lcel_parcial,
                          criar_lcel_robusta)
from pedro.laboratorio import CORRETA, SAIDAS_QUEBRADAS, SOLICITACAO, comparar_estilos, ensaiar

REPARADOR = RunnableLambda(lambda prompt: json.dumps(CORRETA))


def test_cada_saida_quebrada_e_resolvida_pela_camada_prevista():
    relatorio = ensaiar(REPARADOR)
    assert [(c["caso"], c["camada_observada"]) for c in relatorio] == [
        (nome, camada) for nome, (_, camada) in SAIDAS_QUEBRADAS.items()]
    assert all(c["reparos"] <= 1 for c in relatorio)


def test_o_reparo_recebe_solicitacao_saida_e_erro():
    visto = {}

    def reparador(prompt):
        visto["humano"] = prompt.to_messages()[-1].content
        return json.dumps(CORRETA)

    cadeia = criar_lcel_robusta(RunnableLambda(lambda _: SAIDAS_QUEBRADAS["quantidade negativa"][0]),
                                RunnableLambda(reparador))
    assert cadeia.invoke({"texto": SOLICITACAO}).solicitacao.quantidade == 2
    assert SOLICITACAO in visto["humano"] and '"quantidade": -2' in visto["humano"]
    assert "greater than 0" in visto["humano"]


def test_um_reparo_que_tambem_falha_nao_e_publicado():
    cadeia = criar_lcel_robusta(RunnableLambda(lambda _: "não é JSON"),
                                RunnableLambda(lambda _: "continua sem ser JSON"))
    with pytest.raises(OutputParserException):
        cadeia.invoke({"texto": SOLICITACAO})


def test_os_faltantes_sao_calculados_pelo_codigo_nao_pelo_modelo():
    saida = SAIDAS_QUEBRADAS["faltantes mal declarados"][0]
    assert json.loads(saida)["faltantes"] == []
    cadeia = criar_lcel_robusta(RunnableLambda(lambda _: saida), REPARADOR)
    assert cadeia.invoke({"texto": SOLICITACAO}).faltantes == ["quantidade"]


def test_o_parser_sozinho_perde_um_dado_em_silencio_e_a_cadeia_robusta_o_evita():
    truncada = SAIDAS_QUEBRADAS["JSON truncado"][0]
    with pytest.raises(ValueError):
        json.loads(truncada)
    simples = criar_lcel(RunnableLambda(lambda _: truncada)).invoke({"texto": SOLICITACAO})
    assert simples.solicitacao.prazo_max_dias is None  # o prazo de 7 dias desapareceu sem erro
    robusta = criar_lcel_robusta(RunnableLambda(lambda _: truncada), REPARADOR)
    assert robusta.invoke({"texto": SOLICITACAO}).solicitacao.prazo_max_dias == 7


def test_cadeia_imperativa_e_declarativa_sao_equivalentes_no_laboratorio():
    declarativa = ensaiar(REPARADOR, criar_lcel_robusta)
    imperativa = ensaiar(REPARADOR, criar_chain_robusta)
    assert imperativa == declarativa


def test_chain_decorada_expoe_invoke_batch_e_stream():
    modelo = RunnableLambda(lambda _: json.dumps(CORRETA))
    decorada = criar_chain(modelo)
    entrada = {"texto": SOLICITACAO}
    um = decorada.invoke(entrada)
    assert decorada.batch([entrada, entrada]) == [um, um]
    assert list(decorada.stream(entrada)) == [um]  # um único fragmento: o parser precisa de tudo


def test_stream_emite_estados_parciais_se_o_modelo_e_o_parser_transmitem():
    texto = json.dumps(CORRETA)

    def modelo_por_pedacos(_):
        for inicio in range(0, len(texto), 12):
            yield texto[inicio:inicio + 12]

    estados = list(criar_lcel_parcial(RunnableLambda(modelo_por_pedacos)).stream({"texto": SOLICITACAO}))
    assert len(estados) > 3 and estados[-1] == CORRETA
    assert estados[0] != estados[-1]


def test_os_dois_estilos_dao_o_mesmo_resultado_mas_o_rastro_ve_coisas_diferentes():
    lcel, imperativa = comparar_estilos().values()
    assert lcel["resultado_apos_reparar"] == imperativa["resultado_apos_reparar"] == 2
    assert lcel["o_erro_fica_no_rastro"] and not imperativa["o_erro_fica_no_rastro"]
    assert lcel["a_validacao_de_dominio_fica_no_rastro"]
    assert not imperativa["a_validacao_de_dominio_fica_no_rastro"]
    assert lcel["o_grafo_mostra_o_reparo"] and not imperativa["o_grafo_mostra_o_reparo"]
    assert lcel["passos_rastreados_com_reparo"] > imperativa["passos_rastreados_com_reparo"]
