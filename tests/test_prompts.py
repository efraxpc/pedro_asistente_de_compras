import pytest

from pedro.chains import PROMPT, criar_lcel
from pedro.prompts import (EXEMPLOS_ACOES, EXEMPLOS_EXTRACAO, MODELO_AGENTE,
                           MODELO_EXTRACAO, MODELO_EXTRACAO_COT,
                           MODELO_EXTRACAO_FEWSHOT)


def test_modelo_de_extracao_declara_as_suas_variaveis_e_e_reutilizado():
    assert sorted(MODELO_EXTRACAO.input_variables) == ["formato", "texto"]
    assert PROMPT is MODELO_EXTRACAO
    assert criar_lcel(lambda prompt: "{}").first.messages == MODELO_EXTRACAO.messages
    sistema, humano = MODELO_EXTRACAO.format_messages(
        texto="Compare 2 unidades de PEC-01-0001", formato="JSON")
    assert (sistema.type, humano.type) == ("system", "human")
    assert humano.content == "Compare 2 unidades de PEC-01-0001"
    assert "PEC-01-0001" not in sistema.content


def test_modelo_do_agente_admite_qualquer_cenario():
    assert {"dataset_id", "exemplos", "formato", "input", "agent_scratchpad"} <= set(
        MODELO_AGENTE.input_variables)
    for dataset_id in ("cenario-a", "cenario-b"):
        sistema = MODELO_AGENTE.format_messages(
            dataset_id=dataset_id, exemplos=EXEMPLOS_ACOES, formato="JSON",
            input="olá", agent_scratchpad=[])[0]
        assert dataset_id in sistema.content
        assert all(f"{parte}:" in sistema.content
                   for parte in ("Persona", "Tarefa", "Contexto", "Formato"))


@pytest.mark.parametrize("faltante", ["texto", "formato"])
def test_modelo_falha_se_falta_uma_variavel(faltante):
    valores = {"texto": "Preciso de um filtro", "formato": "JSON"}
    del valores[faltante]
    with pytest.raises(KeyError):
        MODELO_EXTRACAO.format_messages(**valores)


def test_few_shot_insere_os_exemplos_como_turnos_resolvidos():
    mensagens = MODELO_EXTRACAO_FEWSHOT.format_messages(texto="Preciso de um filtro", formato="JSON")
    tipos = [m.type for m in mensagens]
    assert tipos == ["system"] + ["human", "ai"] * len(EXEMPLOS_EXTRACAO) + ["human"]
    assert mensagens[-1].content == "Preciso de um filtro"
    assert all("raciocinio" not in m.content for m in mensagens if m.type == "ai")


def test_cot_poe_o_raciocinio_antes_dos_dados():
    mensagens = MODELO_EXTRACAO_COT.format_messages(texto="Preciso de um filtro", formato="JSON")
    respostas = [m.content for m in mensagens if m.type == "ai"]
    assert len(respostas) == len(EXEMPLOS_EXTRACAO)
    assert all(r.index("raciocinio") < r.index("solicitacao") for r in respostas)
    assert "passo a passo" in mensagens[0].content


def test_os_exemplos_ensinam_que_um_dado_ausente_nao_e_zero():
    sem_quantidade = next(e for e in EXEMPLOS_EXTRACAO if e["faltantes"] == ["quantidade"])
    assert "quantidade" not in sem_quantidade["solicitacao"]
