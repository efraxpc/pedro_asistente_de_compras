"""APIs clássicas isoladas para as demonstrações do curso."""
import re
from typing import Any

from langchain_classic.agents import AgentType, initialize_agent
from langchain_classic.chains.router.base import RouterChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.tools import Tool

from .catalog import Cenario, buscar, ofertas


class RouterCompras(RouterChain):
    @property
    def input_keys(self) -> list[str]:
        return ["input"]

    def _call(self, inputs: dict[str, Any], run_manager=None) -> dict[str, Any]:
        texto = inputs["input"].lower()
        destino = ("comparacao" if any(x in texto for x in ("oferta", "preço", "preco", "estoque"))
                   else "catalogo")
        return {"destination": destino, "next_inputs": {"input": inputs["input"]}}


DESTINOS = {
    "catalogo": "buscar ou descrever uma peça por nome, SKU ou ID, sem falar de preços",
    "comparacao": "preços, custos, ofertas, fornecedores, estoque ou prazos de uma peça",
    "cep": "confirmar a cidade ou o estado de um código postal brasileiro (CEP)",
}


def criar_router_llm(llm) -> RouterChain:
    """Router dinâmico: o modelo escolhe o destino lendo a descrição de cada rota."""
    from langchain_classic.chains.router.llm_router import LLMRouterChain, RouterOutputParser
    from langchain_classic.chains.router.multi_prompt_prompt import MULTI_PROMPT_ROUTER_TEMPLATE
    from langchain_core.prompts import PromptTemplate

    destinos = "\n".join(f"{nome}: {descricao}" for nome, descricao in DESTINOS.items())
    modelo = PromptTemplate(template=MULTI_PROMPT_ROUTER_TEMPLATE.format(destinations=destinos),
                            input_variables=["input"], output_parser=RouterOutputParser())
    return LLMRouterChain.from_llm(llm, modelo)


def executar_rota(router: RouterChain, cenario: Cenario, pergunta: str, *,
                  cep_simulado: bool = True) -> dict:
    """Cadeia sequencial: decide a rota e executa a cadeia desse destino."""
    from .integrations import consultar_cep

    rota = router.invoke({"input": pergunta})["destination"] or "esclarecimento"
    if rota == "catalogo":
        return {"rota": rota, "resultado": buscar(cenario, pergunta)}
    if rota == "comparacao":
        ids = re.findall(r"PEC-[0-9]{2}-[0-9]{4}", pergunta.upper())
        return {"rota": rota, "resultado": [o.model_dump() for o in ofertas(cenario, ids[0])]
                if ids else []}
    if rota == "cep":
        codigos = re.findall(r"\b\d{5}-?\d{3}\b", pergunta)
        return {"rota": rota, "resultado": consultar_cep(codigos[0].replace("-", ""),
                                                         simulado=cep_simulado) if codigos else {}}
    return {"rota": "esclarecimento", "resultado": "Você procura uma peça, as ofertas dela ou um CEP?"}


SUFIXO_COM_MEMORIA = """Conversa anterior (use-a para entender a qual peça o usuário se refere):
{chat_history}

Comece.

Question: {input}
Thought:{agent_scratchpad}"""


def criar_react_textual(llm, cenario: Cenario, *, memoria_no_prompt: bool = True):
    """Agente ReAct clássico (zero-shot) com duas ferramentas do catálogo e memória de buffer.

    O prompt zero-shot original não inclui o histórico: a memória é salva, mas o modelo
    não a lê. Com `memoria_no_prompt`, `{chat_history}` é acrescentado ao sufixo do prompt.
    """
    memoria = ConversationBufferMemory(memory_key="chat_history", input_key="input", output_key="output")

    def ofertas_da_peca(texto: str) -> str:
        ids = re.findall(r"PEC-[0-9]{2}-[0-9]{4}", texto.upper())
        if not ids:
            return "Informe um ID com formato PEC-00-0000."
        return str([{"fornecedor": o.fornecedor_nome, "preco_unitario_centavos": o.preco_unitario_centavos,
                     "estoque": o.estoque, "prazo_dias": o.prazo_dias} for o in ofertas(cenario, ids[0])])

    lista = [
        Tool(name="buscar_peca", func=lambda texto: str(buscar(cenario, texto, 5)),
             description="Busca peças fictícias por nome, SKU ou ID. Entrada: texto de busca."),
        Tool(name="ofertas_da_peca", func=ofertas_da_peca,
             description="Devolve fornecedor, preço, estoque e prazo de uma peça. Entrada: o ID PEC-00-0000 dela."),
    ]
    extra = ({"suffix": SUFIXO_COM_MEMORIA,
              "input_variables": ["input", "chat_history", "agent_scratchpad"]}
             if memoria_no_prompt else {})
    agente = initialize_agent(lista, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                              memory=memoria, verbose=False, agent_kwargs=extra,
                              return_intermediate_steps=True, handle_parsing_errors=True,
                              max_iterations=5)
    return agente, memoria


MODELO_CHATBOT = """Você é Pedro, assistente de um catálogo fictício de peças de reposição de eletrodomésticos.
Ajude a definir uma solicitação de compra: peça, quantidade, orçamento e prazo. Não invente
preços nem estoque: diga que serão consultados no catálogo. Responda em uma ou duas frases e lembre
o que o usuário já disse.

Conversa até agora:
{history}
Usuário: {input}
Pedro:"""


def criar_chatbot_buffer(llm):
    """Chatbot conversacional clássico: ConversationChain com ConversationBufferMemory.

    A memória de buffer guarda a conversa completa e a insere inteira em cada prompt.
    """
    from langchain_classic.chains import ConversationChain
    from langchain_core.prompts import PromptTemplate

    memoria = ConversationBufferMemory(human_prefix="Usuário", ai_prefix="Pedro")
    cadeia = ConversationChain(
        llm=llm, memory=memoria,
        prompt=PromptTemplate(template=MODELO_CHATBOT, input_variables=["history", "input"]))
    return cadeia, memoria
