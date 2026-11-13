"""A interface Streamlit conectada ao agente final, conduzida com AppTest.

Executa o app.py de verdade (sem navegador): escreve no chat e muda de conversa.
Requer OPENAI_API_KEY. Usa uma pasta de dados própria para não tocar nas conversas do
usuário, e habilita o índice de políticas salvo, que é próprio e tem manifesto.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TURNOS = ["Preciso de 5 unidades de PEC-01-0001 com prazo máximo de 7 dias",
          "Agora que sejam 6 e mantenha o prazo",
          "A que cidade corresponde o CEP 01001000?",
          "Posso receber em várias caixas?"]


def _mensagens(app) -> list[dict]:
    return [{"papel": m.name, "texto": m.markdown[0].value if m.markdown else ""}
            for m in app.chat_message]


def _ultima_resposta(app) -> dict:
    """O que a interface desenhou na última resposta: passos, cartões, avisos e texto."""
    mensagem = app.chat_message[-1]
    return {"passos": [s.label for s in mensagem.status],
            "cartoes": {m.label: m.value for m in mensagem.metric},
            "conselho_ou_aviso": [a.value for a in [*mensagem.info, *mensagem.warning]],
            "tabelas": len(mensagem.dataframe),
            "texto": " ".join(m.value for m in mensagem.markdown)[:400],
            "erros": [e.value for e in mensagem.error]}


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/rastros/r28_streamlit.json")
    saida = argumentos.parse_args().saida
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY; sem execução remota")
    os.chdir(ROOT)
    os.environ["PEDRO_STORAGE"] = f"storage/evidencias/r28-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
    os.environ["PEDRO_TRUST_POLICY_INDEX"] = "true"
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    app.run()
    relatorio: dict = {
        "tema": "interface Streamlit",
        "modo": "app.py executado com streamlit.testing.v1.AppTest; agente real remoto (OpenAI, ViaCEP); "
                "NLI real local; índice de políticas carregado do disco",
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo_llm": os.getenv("PEDRO_MODEL", "gpt-4.1-mini"),
        "inicializacao": {"titulos": [t.value for t in app.title],
                          "excecoes": [str(e.value) for e in app.exception]},
    }
    chat = []
    for texto in TURNOS:
        app.chat_input[0].set_value(texto).run()
        resposta = _ultima_resposta(app)
        chat.append({"usuario": texto, **resposta})
        print("chat |", texto, "->", resposta["passos"], "|", resposta["cartoes"] or resposta["texto"][:110])
    relatorio["vista_chat"] = {"turnos": chat, "mensagens_na_tela": len(_mensagens(app))}
    primeira_sessao = app.session_state["sessao"]

    # Novo chat: mesmo app, sessão diferente e tela vazia.
    next(b for b in app.sidebar.button if b.label == "Novo chat").click().run()
    relatorio["novo_chat"] = {"sessao_diferente": app.session_state["sessao"] != primeira_sessao,
                              "mensagens_na_tela": len(_mensagens(app))}
    # Reabrir a conversa anterior pela barra lateral: o histórico volta.
    next(b for b in app.sidebar.button if b.key == f"sessao_{primeira_sessao}").click().run()
    reaberta = _mensagens(app)
    relatorio["conversa_reaberta"] = {
        "mensagens_na_tela": len(reaberta),
        "primeira_mensagem": reaberta[0]["texto"] if reaberta else None,
        "cartoes_redesenhados": sum(len(m.metric) for m in app.chat_message)}
    print("novo chat:", relatorio["novo_chat"], "| reaberta:", len(reaberta), "mensagens")

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("salvo em", saida)


if __name__ == "__main__":
    main()
