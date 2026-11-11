"""Anatomia observável do agente: é lida dos objetos reais, não é redigida à mão."""
import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from .agent import criar_agente
from .catalog import Cenario, listar
from .memory import JANELA_MENSAGENS, MODELO_LEMBRANCAS
from .nli import MODELO as MODELO_NLI, REVISAO as REVISAO_NLI
from .policy_demo import ORIGEM as ORIGEM_DEMO, fragmentos_demo

MODELO_LLM_PADRAO = "gpt-4.1-mini"
# Papel de cada ferramenta na anatomia e tipo de lógica que executa.
PAPEIS = {
    "buscar_produtos": ("sensor", "determinística (SQL de leitura)"),
    "consultar_catalogo": ("sensor", "text-to-query (plano com ID; SQL validado para perguntas abertas)"),
    "consultar_politicas": ("sensor", "semântica (FAISS)"),
    "consultar_cep": ("sensor", "API externa (ViaCEP)"),
    "comparar_ofertas": ("cálculo", "determinística (centavos inteiros)"),
    "salvar_preferencia": ("escrita", "determinística (somente citação explícita)"),
}


def descrever_anatomia(cenario: Cenario, memoria_db: Path, user_id: str = "anatomia") -> dict:
    """Devolve os componentes do agente final tal como ficam construídos."""
    # O modelo de preenchimento nunca é invocado: só permite construir o executor sem credenciais.
    executor = criar_agente(cenario, memoria_db, user_id, "", RunnableLambda(lambda x: x))
    passos = getattr(executor.agent, "runnable").steps
    prompt = next(passo for passo in passos if isinstance(passo, ChatPromptTemplate))
    sistema = prompt.messages[0].prompt.template
    return {
        "motor_cognitivo": {"classe": "ChatOpenAI",
                            "modelo": os.getenv("PEDRO_MODEL", MODELO_LLM_PADRAO),
                            "disponivel": bool(os.getenv("OPENAI_API_KEY"))},
        "orquestrador": {"agente": "create_openai_tools_agent", "executor": type(executor).__name__,
                         "max_iteracoes": executor.max_iterations,
                         "historico": "RunnableWithMessageHistory"},
        "system_message": {
            "ptcf": {parte: f"{parte}:" in sistema
                     for parte in ("Persona", "Tarefa", "Contexto", "Formato")},
            "variaveis": sorted(prompt.input_variables),
            "variaveis_fixadas": sorted(prompt.partial_variables),
            "mensagens": [type(m).__name__ for m in prompt.messages],
        },
        "ferramentas": [{"nome": f.name, "papel": PAPEIS[f.name][0],
                         "logica": PAPEIS[f.name][1], "descricao": f.description,
                         "argumentos": sorted(f.args)} for f in executor.tools],
        "memoria": {"curto_prazo": f"janela de {JANELA_MENSAGENS} mensagens + rascunho por sessão",
                    "longo_prazo": "preferências explícitas + episódios vetoriais por usuário",
                    "modelo_embeddings": MODELO_LEMBRANCAS},
        "base_conhecimento": {"dataset_id": cenario.dataset_id,
                              "pecas": listar(cenario)[0],
                              "fragmentos_politicas": len(fragmentos_demo()),
                              "origem_politicas": ORIGEM_DEMO},
        "porta_publicacao": {"verificacao": "exata (total, estoque, orçamento, prazo, IDs, fontes)",
                             "nli": MODELO_NLI, "revisao_nli": REVISAO_NLI},
    }


# Prefixo do módulo importado -> peça do orquestrador que ele fornece.
PECAS_LANGCHAIN = {
    "langchain_core.prompts": "modelos de prompt",
    "langchain_core.output_parsers": "parsers de saída",
    "langchain_core.exceptions": "parsers de saída",
    "langchain_core.runnables": "composição (Runnable, LCEL, @chain)",
    "langchain_core.tools": "ferramentas",
    "langchain_core.callbacks": "callbacks e rastros",
    "langchain_core.messages": "mensagens e histórico",
    "langchain_core.chat_history": "mensagens e histórico",
    "langchain_core.documents": "documentos e embeddings",
    "langchain_core.embeddings": "documentos e embeddings",
    "langchain_classic.agents": "agentes e executor",
    "langchain_classic.chains": "cadeias clássicas (RouterChain)",
    "langchain_classic.memory": "memória clássica",
    "langchain_community.vectorstores": "armazém vetorial (FAISS)",
    "langchain_community.embeddings": "documentos e embeddings",
    "langchain_text_splitters": "divisão de documentos",
    "langchain_openai": "modelo de chat (OpenAI)",
}


def inventario_langchain(raiz: Path | None = None) -> dict[str, dict[str, list[str]]]:
    """Lista quais peças do LangChain o projeto usa, lendo os imports do código.

    Devolve, por peça, os nomes importados e os arquivos que os usam.
    """
    import ast

    raiz = raiz or Path(__file__).resolve().parents[2]
    inventario: dict[str, dict[str, set[str]]] = {}
    for arquivo in sorted([*(raiz / "src/pedro").glob("*.py"), raiz / "app.py"]):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if not isinstance(no, ast.ImportFrom) or not no.module:
                continue
            peca = next((nome for prefixo, nome in PECAS_LANGCHAIN.items()
                         if no.module.startswith(prefixo)), None)
            if peca is None:
                continue
            registro = inventario.setdefault(peca, {"nomes": set(), "arquivos": set()})
            registro["nomes"].update(alias.name for alias in no.names)
            registro["arquivos"].add(arquivo.name)
    return {peca: {chave: sorted(valores) for chave, valores in registro.items()}
            for peca, registro in sorted(inventario.items())}
