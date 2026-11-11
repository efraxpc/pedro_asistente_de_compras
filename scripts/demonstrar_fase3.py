"""Fase 3 com o modelo real: chatbot com memória, intenções e entidades, conversa complexa.

Requer OPENAI_API_KEY. Chama a OpenAI e o ViaCEP; o catálogo e as políticas são sintéticos.
Cada bloco salva o que foi observado; nada é simulado.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pedro.agent import Rastro, criar_fluxo
from pedro.catalog import criar_cenario
from pedro.chains import criar_variantes_de_prompt
from pedro.dialogue import interpretar_compra
from pedro.legacy import criar_chatbot_buffer
from pedro.memory import (FastEmbedder, Historico, ler_rascunho, mapa_memorias, nova_sessao,
                          preferencias, recuperar)
from pedro.nli import ModeloNLI
from pedro.rag import carregar_indice, inspecionar_indice

ROOT = Path(__file__).resolve().parents[1]
CHATBOT = ["Olá, sou a Ana. Preciso de um termostato para a minha geladeira.",
           "Que sejam 2 unidades.",
           "Tenho até R$ 900 e preciso dele em 5 dias.",
           "Resuma a minha solicitação completa e diga como eu me chamo."]
MENSAGENS = ["Compare 2 unidades de PEC-01-0001 até R$ 5.000 em 7 dias",
             "Preciso de um termostato para geladeira",
             "A que cidade corresponde o CEP 01001000?",
             "O que diz a política de devoluções?",
             "Prefiro fornecedores nacionais, lembre-se disso",
             "Quero meia dúzia de PEC-02-0001 sem limite de gasto",
             "Olá, o que você pode fazer?"]
COMPLEXA = ["Preciso de 2 unidades de PEC-01-0001 com prazo máximo de 7 dias",
            "Agora que sejam 5 e mantenha o prazo",
            "Melhor sem limite de prazo, mas com orçamento de R$ 10.000",
            "Prefiro fornecedores nacionais, lembre-se disso",
            "A que cidade corresponde o CEP 01001000?",
            "Como se verifica a compatibilidade elétrica antes de instalar uma peça?",
            "Volte a comparar com o último que eu pedi",
            "Compare 2 unidades de PEC-11-0001"]


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/fase3_memoria_llm.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_openai import ChatOpenAI

    modelo = os.getenv("PEDRO_MODEL", "gpt-4.1-mini")
    llm = ChatOpenAI(model=modelo, temperature=0)
    cenario = criar_cenario(ROOT / "storage/evidencias/fase3_catalogos")
    memoria = ROOT / f"storage/evidencias/fase3_memoria-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.sqlite3"

    # R16: chatbot com ConversationBufferMemory.
    chatbot, buffer = criar_chatbot_buffer(llm)
    r16 = []
    for texto in CHATBOT:
        resposta = chatbot.invoke({"input": texto})["response"]
        r16.append({"usuario": texto, "pedro": resposta,
                    "caracteres_na_memoria": len(buffer.load_memory_variables({})["history"])})
        print("R16 |", texto, "->", resposta[:150].replace("\n", " "))

    # R17: intenção e entidades com o modelo (few-shot) e com as regras do chat.
    extrator = criar_variantes_de_prompt(llm)["few-shot"]
    r17 = []
    for texto, extracao in zip(MENSAGENS, extrator.batch([{"texto": t} for t in MENSAGENS])):
        regras = interpretar_compra(cenario, None, texto)
        r17.append({
            "mensagem": texto, "intencao_llm": extracao.intencao,
            "entidades_llm": extracao.solicitacao.model_dump(exclude_none=True),
            "faltantes": extracao.solicitacao.faltantes(),
            "regras_do_chat": None if regras is None else {
                "entidades": regras[0].solicitacao.model_dump(exclude_none=True),
                "esclarecimento": regras[1]}})
        print("R17 |", texto, "->", extracao.intencao,
              extracao.solicitacao.model_dump(exclude_none=True), "| regras:",
              None if regras is None else regras[1])

    # R18 (e R13, R14, R15): conversa complexa com o agente final e a sua memória.
    manifesto = inspecionar_indice(ROOT / "knowledge/politicas")
    indice, _ = carregar_indice(ROOT / "knowledge/politicas", FastEmbedEmbeddings(
        model_name=manifesto["embedding_model"], doc_embed_type="passage"), origem_confiavel=True)
    nli = ModeloNLI()
    usuario = "ana"
    sessao = nova_sessao(memoria, usuario, cenario.dataset_id)
    rastro = Rastro()
    fluxo = criar_fluxo(cenario, memoria, llm=ChatOpenAI(model=modelo), classificador=nli,
                        indice=indice, rastro=rastro)
    r18 = []
    for texto in COMPLEXA:
        desde = len(rastro.eventos)
        resposta = fluxo.invoke({"input": texto}, config={"configurable": {
            "user_id": usuario, "session_id": sessao}}).content
        eventos = rastro.eventos[desde:]
        rascunho = ler_rascunho(memoria, usuario, sessao)
        r18.append({
            "usuario": texto,
            "ferramentas": [e["ferramenta"] + " " + e["entrada"] for e in eventos
                            if e["evento"] == "tool_start"],
            "verificacoes": [e["erros"] for e in eventos if e["evento"] == "verificacao"],
            "rascunho_apos_o_turno": {k: v for k, v in (rascunho or {}).get("solicitacao", {}).items()
                                      if v is not None},
            "resposta_publicada": resposta})
        print("R18 |", texto, "->", [f.split()[0] for f in r18[-1]["ferramentas"]],
              r18[-1]["rascunho_apos_o_turno"], "|", resposta.splitlines()[0][:90])

    # Persistência e isolamento: cria-se outro fluxo (como após reiniciar) sobre a mesma base.
    mapa = mapa_memorias(memoria, usuario, sessao)
    reinicio = Historico(memoria, usuario, sessao)
    outra_sessao = nova_sessao(memoria, usuario, cenario.dataset_id)
    outro_usuario_sessao = nova_sessao(memoria, "luis", cenario.dataset_id)
    pergunta_lembranca = "Qual fornecedor era melhor para mim no compressor PEC-01-0001?"
    embedder = FastEmbedder()
    persistencia = {
        "apos_reiniciar_o_fluxo": {"mensagens_salvas": len(reinicio.todos()),
                                   "janela_que_o_agente_ve": len(reinicio.messages)},
        "sessao_nova_do_mesmo_usuario": {
            "rascunho": ler_rascunho(memoria, usuario, outra_sessao),
            "preferencias": preferencias(memoria, usuario),
            "episodios_recuperados": [{"similaridade": round(float(r["similaridade"]), 3),
                                       "texto": r["texto"][:160]}
                                      for r in recuperar(memoria, usuario, pergunta_lembranca, embedder)]},
        "outro_usuario": {
            "rascunho": ler_rascunho(memoria, "luis", outro_usuario_sessao),
            "preferencias": preferencias(memoria, "luis"),
            "episodios_recuperados": recuperar(memoria, "luis", pergunta_lembranca, embedder)},
        "pergunta_usada_para_recuperar": pergunta_lembranca,
    }
    print("mapa:", json.dumps(mapa, ensure_ascii=False)[:500])
    print("persistência:", json.dumps(persistencia, ensure_ascii=False)[:700])

    relatorio = {
        "fase": 3, "rubricas": ["R13", "R14", "R15", "R16", "R17", "R18"],
        "modo": "real remoto (OpenAI e ViaCEP); NLI e embeddings reais locais; dados sintéticos",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": modelo,
        "r16_chatbot_conversation_buffer_memory": {"turnos": r16,
                                                   "memoria_final": buffer.load_memory_variables({})["history"]},
        "r17_intencao_e_entidades": r17,
        "r18_conversa_complexa": r18,
        "r13_mapa_de_memorias": mapa,
        "r14_r18_persistencia_e_isolamento": persistencia,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("salvo em", saida)


if __name__ == "__main__":
    main()
