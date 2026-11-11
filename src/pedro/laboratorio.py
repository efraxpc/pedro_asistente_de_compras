"""Laboratório de saídas quebradas: defeitos típicos de um LLM diante da cadeia de extração."""
import json

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableLambda

from .chains import criar_chain_robusta, criar_lcel_robusta
from .contracts import Extracao

SOLICITACAO = "Compare 2 unidades de PEC-01-0001 até R$ 5.000 em 7 dias"
DADOS = {"produto_id": "PEC-01-0001", "quantidade": 2,
         "orcamento_centavos": 500000, "prazo_max_dias": 7}
CORRETA = {"intencao": "comparar", "faltantes": [], "solicitacao": DADOS}


def _variante(intencao: str = "comparar", **solicitacao) -> str:
    return json.dumps({"intencao": intencao, "faltantes": [],
                       "solicitacao": {**DADOS, **solicitacao}}, ensure_ascii=False)


# nome -> (saída do modelo, camada que deve resolvê-la)
SAIDAS_QUEBRADAS: dict[str, tuple[str, str]] = {
    "JSON válido": (_variante(), "nenhuma"),
    "cercas markdown e conversa": ("Claro, aqui está:\n```json\n" + _variante()
                                   + "\n```\nEspero que ajude.", "parser"),
    "JSON truncado": (_variante()[:-12], "reparo"),
    "quantidade por extenso": (_variante(quantidade="dois"), "reparo"),
    "quantidade negativa": (_variante(quantidade=-2), "reparo"),
    "intenção fora da lista": (_variante(intencao="comprar"), "reparo"),
    "texto livre sem JSON": ("Não posso responder em JSON, mas você quer 2 compressores.",
                             "reparo"),
    "faltantes mal declarados": (_variante(quantidade=None), "regra de domínio"),
}


def ensaiar(reparador, construtor=criar_lcel_robusta) -> list[dict]:
    """Passa cada saída quebrada pela cadeia robusta e registra qual camada a resolveu.

    O gerador é um duplo que emite a saída quebrada; `reparador` é o modelo que repara
    (real ou duplo). `construtor` escolhe a cadeia: declarativa ou imperativa. A camada é
    deduzida do que foi observado, não do rótulo esperado.
    """
    relatorio = []
    for nome, (saida, esperada) in SAIDAS_QUEBRADAS.items():
        reparos = []

        def contar(prompt, registro=reparos):
            registro.append(1)
            return prompt

        cadeia = construtor(RunnableLambda(lambda _, texto=saida: texto),
                            RunnableLambda(contar) | reparador)
        try:
            resultado: Extracao | None = cadeia.invoke({"texto": SOLICITACAO})
            erro = None
        except Exception as exc:
            resultado, erro = None, type(exc).__name__
        if erro:
            camada = "sem resolver"
        elif reparos:
            camada = "reparo"
        elif resultado is not None and resultado.faltantes:
            camada = "regra de domínio"
        elif saida.strip().startswith("{"):
            camada = "nenhuma"
        else:
            camada = "parser"
        relatorio.append({"caso": nome, "camada_esperada": esperada, "camada_observada": camada,
                          "reparos": len(reparos), "erro": erro,
                          "resultado": resultado.model_dump(exclude_none=True) if resultado else None})
    return relatorio


class _PassosRastreados(BaseCallbackHandler):
    """Anota cada passo que o rastro do LangChain chega a ver."""

    def __init__(self):
        self.passos: list[str] = []

    def on_chain_start(self, serialized, inputs, *, name=None, **kwargs) -> None:
        self.passos.append(name or "passo")

    def on_chain_error(self, error, **kwargs) -> None:
        self.passos.append("ERRO:" + type(error).__name__)


def comparar_estilos() -> dict[str, dict]:
    """Mede o que cada estilo da mesma cadeia com reparo deixa ver.

    Usa duplos: não chama nenhum modelo. Executa um caso sem falha e outro com reparo
    e conta os passos que o rastro registra e os nós do grafo.
    """
    correta = json.dumps(CORRETA)
    reparador = RunnableLambda(lambda _: correta)
    medidas = {}
    for estilo, construtor in (("declarativa (LCEL)", criar_lcel_robusta),
                               ("imperativa (@chain)", criar_chain_robusta)):
        registro = {}
        for caso, saida in (("sem_falha", correta),
                            ("com_reparo", SAIDAS_QUEBRADAS["quantidade negativa"][0])):
            rastro = _PassosRastreados()
            cadeia = construtor(RunnableLambda(lambda _, texto=saida: texto), reparador)
            resultado = cadeia.invoke({"texto": SOLICITACAO}, config={"callbacks": [rastro]})
            registro[caso] = {"passos": rastro.passos, "quantidade": resultado.solicitacao.quantidade}
        nos = [no.name for no in cadeia.get_graph().nodes.values()]
        medidas[estilo] = {
            "passos_rastreados_sem_falha": len(registro["sem_falha"]["passos"]),
            "passos_rastreados_com_reparo": len(registro["com_reparo"]["passos"]),
            "o_erro_fica_no_rastro": any(
                passo.startswith("ERRO") for passo in registro["com_reparo"]["passos"]),
            "a_validacao_de_dominio_fica_no_rastro": "_validar" in registro["sem_falha"]["passos"],
            "o_grafo_mostra_o_reparo": "WithFallbacks" in nos,
            "resultado_apos_reparar": registro["com_reparo"]["quantidade"],
            "passos_com_reparo": registro["com_reparo"]["passos"],
        }
    return medidas
