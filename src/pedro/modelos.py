"""Modelo de chat do agente, escolhido pelo arquivo .env.

Por padrão usa a OpenAI. Com PEDRO_BASE_URL aponta para qualquer servidor compatível com a
API da OpenAI, por exemplo um modelo local no Ollama (http://localhost:11434/v1). O resto do
projeto não muda: as mesmas ferramentas, a mesma guarda de entrada e as mesmas verificações.
"""
import os

MODELO_PADRAO = "gpt-4.1-mini"


def base_local() -> str | None:
    """Endereço do servidor compatível configurado, ou None se o agente usa a OpenAI."""
    return (os.getenv("PEDRO_BASE_URL") or "").strip() or None


def nome_do_modelo() -> str:
    return os.getenv("PEDRO_MODEL", MODELO_PADRAO)


def ha_modelo() -> bool:
    """Indica se há um modelo configurado: uma chave da OpenAI ou um servidor local."""
    return bool(os.getenv("OPENAI_API_KEY") or base_local())


def criar_llm(**opcoes):
    """Cria o modelo de chat configurado. Um servidor local não precisa de chave."""
    from langchain_openai import ChatOpenAI

    base = base_local()
    if base:
        return ChatOpenAI(model=nome_do_modelo(), base_url=base,
                          api_key=os.getenv("PEDRO_LOCAL_API_KEY", "local"), **opcoes)
    return ChatOpenAI(model=nome_do_modelo(), **opcoes)
