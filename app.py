"""Interface local: chat que compara fornecedores de peças fictícias."""
import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pedro.agent import Rastro, criar_fluxo, e_diagnostico_t24, partes_de
from pedro.business import brl, descrever_motivos, variacao_percentual
from pedro.catalog import abrir_cenario, criar_cenario
from pedro.contracts import Alternativa, Oferta, RespostaCompra
from pedro.memory import (MODELO_LEMBRANCAS, Historico, apagar_sessao, apagar_sessoes, nova_sessao,
                          sessoes)
from pedro.policy_demo import PERGUNTA_T24_ORIGINAL, criar_indice_demo, impressao_corpus
from pedro.precos import aviso_de_preco
from pedro.verification import melhor_sem_preferencia

load_dotenv()
BASE = Path(os.getenv("PEDRO_STORAGE", "storage"))
CATALOGOS = BASE / "catalogos"
MEMORIA = BASE / "memoria.sqlite3"
USUARIO = "usuario-demo"
CONVERSAS_VISIVEIS = 8
st.set_page_config(page_title="Pedro · assistente de compras", page_icon=":material/shopping_cart:",
                   layout="wide")


@st.cache_resource(show_spinner=False, max_entries=1)
def modelo_nli():
    from pedro.nli import ModeloNLI
    return ModeloNLI()


@st.cache_resource(show_spinner=False, max_entries=2)
def indice_politicas(pasta: str, impressao_conteudo: str, modelo: str):
    from pedro.rag import carregar_indice
    if modelo == MODELO_LEMBRANCAS:
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        embeddings = FastEmbedEmbeddings(model_name=modelo, doc_embed_type="passage")
    else:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(model=modelo)
    return carregar_indice(Path(pasta), embeddings,
                           origem_confiavel=True)[0]


@st.cache_resource(show_spinner=False, max_entries=1)
def indice_politicas_demo(impressao_conteudo: str):
    return criar_indice_demo()


def novo_cenario() -> None:
    st.session_state.cenario = criar_cenario(CATALOGOS)
    st.session_state.sessao = nova_sessao(MEMORIA, USUARIO, st.session_state.cenario.dataset_id)


def novo_chat() -> None:
    st.session_state.sessao = nova_sessao(MEMORIA, USUARIO, st.session_state.cenario.dataset_id)


def esquecer_apagar() -> None:
    """Fecha o pedido de apagar: ao cancelar, ao confirmar ou ao fechar o diálogo."""
    st.session_state.apagar_pendente = None


@st.dialog("Apagar conversa", icon=":material/delete:", on_dismiss=esquecer_apagar)
def confirmar_apagar(session_id: str, titulo: str) -> None:
    """Pede confirmação antes de apagar uma conversa: a ação não tem volta."""
    st.markdown(f"Apagar a conversa «{titulo}»?")
    st.caption("Saem as mensagens, o rascunho de compra e as lembranças dessa conversa. "
               "As suas preferências salvas ficam.")
    with st.container(horizontal=True):
        if st.button("Apagar", type="primary", icon=":material/delete:", key="confirmar_apagar"):
            esquecer_apagar()
            apagar_sessao(MEMORIA, USUARIO, session_id)
            st.session_state.passos = {chave: valor for chave, valor in st.session_state.passos.items()
                                       if chave[0] != session_id}
            if session_id == st.session_state.sessao:
                novo_chat()
            st.rerun()
        if st.button("Cancelar", key="cancelar_apagar"):
            esquecer_apagar()
            st.rerun()


@st.dialog("Apagar todas as conversas", icon=":material/delete_sweep:", on_dismiss=esquecer_apagar)
def confirmar_apagar_todas(quantas: int) -> None:
    """Pede confirmação antes de apagar todas as conversas do usuário."""
    st.markdown(f"Apagar as {quantas} conversas?" if quantas != 1 else "Apagar a única conversa?")
    st.caption("Saem as mensagens, os rascunhos de compra e as lembranças de todas as conversas. "
               "As suas preferências salvas ficam.")
    with st.container(horizontal=True):
        if st.button("Apagar todas", type="primary", icon=":material/delete_sweep:",
                     key="confirmar_apagar_todas"):
            esquecer_apagar()
            apagar_sessoes(MEMORIA, USUARIO)
            st.session_state.passos = {}
            novo_chat()
            st.rerun()
        if st.button("Cancelar", key="cancelar_apagar_todas"):
            esquecer_apagar()
            st.rerun()


def reabrir(session_id: str, dataset_id: str) -> None:
    st.session_state.sessao = session_id
    try:
        st.session_state.cenario = abrir_cenario(CATALOGOS, dataset_id)
        st.session_state.erro_cenario = None
    except (FileNotFoundError, ValueError):
        st.session_state.cenario = None
        st.session_state.erro_cenario = "O cenário desta conversa não está mais disponível."


def sugerir(texto: str) -> None:
    st.session_state.sugerida = texto


# --- Apresentação de uma comparação de fornecedores ---------------------------------------

def origem(oferta: Oferta) -> str:
    return "Nacional" if oferta.nacional else "Internacional"


def frente_a_media(oferta: Oferta) -> str:
    if not oferta.preco_medio_centavos:
        return "—"
    pontos = variacao_percentual(oferta.preco_unitario_centavos, oferta.preco_medio_centavos)
    return "igual" if pontos == 0 else f"{pontos:+d} %"


def tabela_de_ofertas(alternativas: list[Alternativa]) -> None:
    """Todas as ofertas comparadas: quem atende, quem não e por quê."""
    st.dataframe(
        [{"Fornecedor": a.oferta.fornecedor_nome, "Origem": origem(a.oferta),
          "Total": brl(a.total_centavos), "Atende": a.atende,
          "Motivo de descarte": descrever_motivos(a) or "—",
          "Preço por unidade": brl(a.oferta.preco_unitario_centavos),
          "Frente à sua média": frente_a_media(a.oferta),
          "Entrega (dias)": a.oferta.prazo_dias, "Pedido mínimo": a.oferta.pedido_minimo,
          "Estoque": a.oferta.estoque, "Oferta": a.oferta.id} for a in alternativas],
        hide_index=True,
        column_config={
            "Atende": st.column_config.CheckboxColumn(help="Atende a estoque, pedido mínimo, prazo e orçamento"),
            "Frente à sua média": st.column_config.TextColumn(
                help="Preço por unidade de hoje frente à média dos meses anteriores"),
            "Oferta": st.column_config.TextColumn(help="Identificador da oferta no catálogo"),
        },
        alt="Ofertas comparadas, com o total, se atendem e o motivo de descarte")


def mostrar_comparacao(resposta: RespostaCompra, conselho: str | None = None,
                       direta: dict | None = None) -> None:
    """Desenha uma comparação verificada: resposta à pergunta, vencedor, aviso de preço e ofertas."""
    solicitacao = resposta.solicitacao
    if direta:
        verificada = direta.get("fonte") == "resposta verificada"
        st.success(direta["texto"], icon=":material/chat:",
                   title="Resposta à sua pergunta · redigida pelo modelo e verificada" if verificada
                   else "Resposta à sua pergunta · resumo calculado pelo sistema")
    if resposta.estado == "sem_oferta":
        st.warning(f"Nenhuma oferta atende para {solicitacao.quantidade} unidades de "
                   f"{solicitacao.produto_id}. A tabela mostra por que cada uma foi descartada.",
                   title="Sem oferta válida", icon=":material/block:")
    else:
        vencedora = next(a for a in resposta.alternativas
                         if a.oferta.fornecedor_id == resposta.fornecedor_id)
        with st.container(horizontal=True):
            st.metric("Fornecedor recomendado", vencedora.oferta.fornecedor_nome, border=True,
                      height="stretch", icon=":material/storefront:")
            st.metric(f"Total por {solicitacao.quantidade} unidades", brl(vencedora.total_centavos),
                      border=True, height="stretch", icon=":material/payments:")
            st.metric("Entrega", f"{vencedora.oferta.prazo_dias} dias", border=True,
                      height="stretch", icon=":material/local_shipping:")
            st.metric("Origem", origem(vencedora.oferta), border=True, height="stretch",
                      icon=":material/public:")
        if conselho:
            st.info(conselho, title="Conselho sobre o preço · redigido pelo modelo e verificado",
                    icon=":material/insights:")
        elif aviso := aviso_de_preco(resposta):
            st.warning(aviso, title="Aviso de preço", icon=":material/trending_up:")
        if solicitacao.origem_preferida:
            # «nacional» → «nacionais», «internacional» → «internacionais».
            nota = ("Foi aplicada a sua preferência por fornecedores "
                    f"{solicitacao.origem_preferida[:-1]}is.")
            barata = melhor_sem_preferencia(resposta)
            if barata is not None:
                nota += (f" Sem ela, a mais barata seria {barata.oferta.fornecedor_nome} "
                         f"por {brl(barata.total_centavos)}.")
            st.info(nota, icon=":material/favorite:")
    tabela_de_ofertas(resposta.alternativas)
    validas = [a for a in resposta.alternativas if a.atende and a.oferta.meses_historico]
    if validas:
        with st.expander("Histórico de preços das ofertas válidas", icon=":material/history:"):
            st.dataframe(
                [{"Fornecedor": a.oferta.fornecedor_nome,
                  "Hoje": brl(a.oferta.preco_unitario_centavos),
                  "Mês anterior": brl(a.oferta.preco_anterior_centavos or 0),
                  f"Média de {a.oferta.meses_historico} meses": brl(a.oferta.preco_medio_centavos or 0),
                  "Frente à sua média": frente_a_media(a.oferta),
                  "Mínimo do período": brl(a.oferta.preco_minimo_centavos or 0),
                  "Máximo do período": brl(a.oferta.preco_maximo_centavos or 0)} for a in validas],
                hide_index=True, alt="Histórico do preço por unidade de cada oferta válida")
            st.caption("O histórico informa: não muda qual oferta vence.")
    st.caption("Fontes: " + ", ".join(a.oferta.id for a in resposta.alternativas))


def mostrar_mensagem(mensagem) -> None:
    """Resposta do assistente: as comparações como cartões e tabela, o resto como texto."""
    for parte in partes_de(mensagem):
        if parte.get("titulo"):
            st.markdown(f"**{parte['titulo']}**")
        if parte.get("comparacao"):
            mostrar_comparacao(RespostaCompra.model_validate(parte["comparacao"]),
                               parte.get("conselho"), parte.get("direta"))
        else:
            st.markdown(parte["texto"])


# --- Passos do agente ----------------------------------------------------------------------

FERRAMENTAS = {
    "buscar_produtos": "Busquei a peça no catálogo",
    "consultar_catalogo": "Consultei o catálogo",
    "comparar_ofertas": "Comparei as ofertas dos fornecedores",
    "consultar_politicas": "Busquei nas políticas",
    "consultar_cep": "Consultei o CEP no ViaCEP",
    "salvar_preferencia": "Salvei a sua preferência",
}
ANCORAGENS = {"comparacao_ancorada": "Peguei os números do cálculo da ferramenta",
              "cep_ancorado": "Peguei a cidade da resposta do ViaCEP",
              "citacoes_ancoradas": "Conferi as citações com o texto da fonte",
              "catalogo_ancorado": "Montei a tabela com as linhas da consulta",
              "preferencia_ancorada": "Confirmei o que foi salvo"}


def descrever_passo(evento: dict) -> dict | None:
    """Converte um evento do rastro em um passo legível; None se não merece ser mostrado."""
    tipo = evento["evento"]
    if tipo == "plano":
        return {"rotulo": f"Dividi a sua mensagem em {len(evento['pedidos'])} pedidos",
                "detalhe": "\n".join(f"- {p['pedido']}" for p in evento["pedidos"])}
    if tipo == "interpretacao":
        leitura = evento.get("modelo") or {}
        if not leitura.get("e_compra"):
            return {"rotulo": "Li a sua mensagem: não é uma compra", "detalhe": ""}
        mudancas = {k: v for k, v in leitura.items() if k != "e_compra" and v not in (None, [])}
        return {"rotulo": "Li a sua mensagem",
                "detalhe": f"Mudanças na solicitação: `{json.dumps(mudancas, ensure_ascii=False)}`"
                if mudancas else "Sem mudanças em quantidade, orçamento nem prazo."}
    if tipo == "tool_start":
        return {"rotulo": FERRAMENTAS.get(evento["ferramenta"], evento["ferramenta"]),
                "detalhe": f"`{evento['ferramenta']}` com `{evento['entrada']}`"}
    if tipo == "verificacao":
        if evento["erros"]:
            return {"rotulo": "A proposta não passou na verificação; pedi outra", "estado": "error",
                    "detalhe": "\n".join(f"- {e}" for e in evento["erros"])}
        return {"rotulo": "Verifiquei a resposta", "detalhe": "Sem erros."}
    if tipo in ANCORAGENS:
        return {"rotulo": ANCORAGENS[tipo], "detalhe": ""}
    if tipo == "conselho_preco":
        if evento.get("fonte") == "conselho verificado":
            return {"rotulo": "Redigi um conselho de preço e o verifiquei", "detalhe": ""}
        return {"rotulo": "Descartei o meu conselho de preço; uso o aviso fixo", "estado": "error",
                "detalhe": "\n".join(f"- {e}" for e in evento.get("erros") or [])}
    if tipo == "guarda":
        if evento.get("segue"):
            return {"rotulo": "Confirmei com o modelo que a mensagem é sobre compras", "detalhe": ""}
        rotulos = {"injecao": "Recusei a mensagem: tenta mudar as minhas instruções",
                   "fora_do_tema": "Recusei a mensagem: não é sobre compras de peças",
                   "cumprimento": "Respondi sem chamar o agente",
                   "longa": "Recusei a mensagem: longa demais", "vazia": "A mensagem veio vazia"}
        return {"rotulo": rotulos.get(evento.get("motivo"), "Recusei a mensagem"),
                "detalhe": f"Camada: {evento.get('camada')} · regra: {evento.get('regra')}"}
    if tipo == "resposta_politica":
        if evento.get("fonte") == "resposta verificada":
            return {"rotulo": "Respondi à sua pergunta com a política e verifiquei a frase", "detalhe": ""}
        return {"rotulo": "Descartei a minha frase; cito a regra literal", "estado": "error",
                "detalhe": "\n".join(f"- {e}" for e in evento.get("erros") or [])}
    if tipo == "comparacao_reutilizada":
        return {"rotulo": "Refiz o cálculo da comparação em andamento, sem chamar o modelo", "detalhe": ""}
    if tipo == "resposta_direta":
        if evento.get("fonte") == "resposta verificada":
            return {"rotulo": "Respondi à sua pergunta e verifiquei a frase", "detalhe": ""}
        return {"rotulo": "Descartei a minha frase; uso o resumo calculado", "estado": "error",
                "detalhe": "\n".join(f"- {e}" for e in evento.get("erros") or [])}
    return None


def mostrar_passo(passo: dict) -> None:
    with st.status(passo["rotulo"], type="step", state=passo.get("estado", "complete")):
        if passo.get("detalhe"):
            st.markdown(passo["detalhe"])


class PassosAoVivo(list):
    """Lista de eventos do rastro que desenha cada passo assim que ele ocorre."""

    def __init__(self):
        super().__init__()
        self.passos: list[dict] = []

    def append(self, evento: dict) -> None:
        super().append(evento)
        passo = descrever_passo(evento)
        if passo is None:
            return
        self.passos.append(passo)
        try:
            mostrar_passo(passo)
        except Exception:  # um passo que não pode ser desenhado não deve quebrar a resposta
            pass


def preparar_agente(teste_t24: bool):
    """Carrega o modelo, o NLI e o índice de políticas disponíveis para este turno."""
    llm = classificador = indice = None
    if os.getenv("OPENAI_API_KEY") and not teste_t24:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=os.getenv("PEDRO_MODEL", "gpt-4.1-mini"))
        try:
            classificador = modelo_nli()
        except Exception:
            st.warning("O modelo NLI não está disponível; as recomendações ficarão bloqueadas.")
    pasta = Path("knowledge/politicas")
    if teste_t24:
        try:
            indice = indice_politicas_demo(impressao_corpus())
        except Exception as exc:
            st.warning(f"Teste T24 não disponível: {type(exc).__name__}")
    elif (pasta / "manifest.json").is_file() and llm is not None:
        if os.getenv("PEDRO_TRUST_POLICY_INDEX", "false").lower() != "true":
            st.warning("Revise a procedência do índice antes de habilitar o seu docstore.")
        else:
            try:
                from pedro.rag import inspecionar_indice
                meta = inspecionar_indice(pasta)
                indice = indice_politicas(str(pasta), json.dumps(meta["sha256"], sort_keys=True),
                                          meta["embedding_model"])
            except (ValueError, FileNotFoundError, PermissionError, KeyError) as exc:
                st.warning(f"Índice de políticas não disponível: {type(exc).__name__}")
    if indice is None and llm is not None:
        try:
            indice = indice_politicas_demo(impressao_corpus())
        except Exception as exc:
            st.warning(f"Políticas fictícias não disponíveis: {type(exc).__name__}")
    return llm, classificador, indice


# --- Estado inicial e barra lateral --------------------------------------------------------

if "cenario" not in st.session_state:
    novo_cenario()
if "erro_cenario" not in st.session_state:
    st.session_state.erro_cenario = None
if "apagar_pendente" not in st.session_state:
    st.session_state.apagar_pendente = None
if "passos" not in st.session_state:
    st.session_state.passos = {}  # (sessão, número da mensagem) -> passos do agente

with st.sidebar:
    st.title(":material/shopping_cart: Pedro")
    st.caption("Assistente de compras · dados fictícios")
    st.button("Novo chat", on_click=novo_chat, icon=":material/edit_square:", width="stretch")
    st.subheader("Conversas")
    conversas = sessoes(MEMORIA, USUARIO)
    for sessao in conversas[:CONVERSAS_VISIVEIS]:
        try:
            primeiro = next((m for m in Historico(MEMORIA, USUARIO, sessao["id"]).todos()
                             if m.type == "human"), None)
        except ValueError:
            primeiro = None
        titulo = str(primeiro.content)[:34] if primeiro else "Conversa nova"
        atual = sessao["id"] == st.session_state.sessao
        coluna_titulo, coluna_apagar = st.columns([5, 1], vertical_alignment="center", gap="small")
        coluna_titulo.button(titulo, key=f"sessao_{sessao['id']}", on_click=reabrir,
                             args=(sessao["id"], sessao["dataset_id"]), width="stretch",
                             type="primary" if atual else "secondary",
                             icon=":material/chat:" if atual else ":material/chat_bubble_outline:",
                             help=f"Sessão {sessao['id'][:8]} · cenário {sessao['dataset_id'][:8]}")
        if coluna_apagar.button(":material/delete:", key=f"apagar_{sessao['id']}", type="tertiary",
                                help=f"Apagar a conversa «{titulo}»"):
            st.session_state.apagar_pendente = (sessao["id"], titulo)
    if len(conversas) > 1:
        if st.button("Apagar todas", key="apagar_todas", icon=":material/delete_sweep:",
                     type="tertiary", width="stretch",
                     help=f"Apaga as {len(conversas)} conversas, depois de confirmar"):
            st.session_state.apagar_pendente = ("todas", "")

# O pedido de apagar fica guardado até confirmar, cancelar ou fechar o diálogo.
pendente = st.session_state.apagar_pendente
if pendente is not None:
    if pendente[0] == "todas":
        confirmar_apagar_todas(len(conversas))
    else:
        confirmar_apagar(*pendente)

cenario = st.session_state.cenario
if cenario is None:
    st.warning(st.session_state.erro_cenario or "Cenário ausente")
    st.stop()
com_agente = bool(os.getenv("OPENAI_API_KEY"))

st.title("Chat")
with st.container(horizontal=True):
    st.badge(f"Cenário {cenario.dataset_id[:8]}", icon=":material/database:", color="gray")
    if com_agente:
        st.badge("Agente ativo", icon=":material/smart_toy:", color="green")
    else:
        st.badge("Modo local, sem modelo", icon=":material/offline_bolt:", color="orange")
    st.badge("Dados comerciais fictícios", icon=":material/science:", color="gray")
mensagens = Historico(MEMORIA, USUARIO, st.session_state.sessao).todos()
# O campo de entrada fica fixo embaixo mesmo declarado aqui; assim já se sabe se há pergunta.
pergunta = st.chat_input("Pergunte sobre peças, ofertas, fornecedores ou políticas", key="pergunta",
                         submit_mode="disable") or st.session_state.pop("sugerida", None)
for numero, mensagem in enumerate(mensagens):
    with st.chat_message("user" if mensagem.type == "human" else "assistant"):
        if mensagem.type == "human":
            st.markdown(str(mensagem.content))
            continue
        passos = st.session_state.passos.get((st.session_state.sessao, numero))
        if passos:
            with st.expander(f"Como cheguei a esta resposta · {len(passos)} passos", type="compact"):
                for passo in passos:
                    mostrar_passo(passo)
        mostrar_mensagem(mensagem)
if not mensagens and not pergunta:
    st.caption("Experimente uma destas perguntas ou escreva a sua.")
    sugestoes = ["Compare 5 unidades de PEC-01-0001 com prazo de 7 dias",
                 "Compare 5 unidades de PEC-02-0189", "Liste as peças"]
    if com_agente:
        sugestoes += [PERGUNTA_T24_ORIGINAL,
                      "A que cidade corresponde o CEP 01001000?",
                      "Quais são as 5 peças de maior potência?"]
    with st.container(horizontal=True):
        for texto in sugestoes:
            st.button(texto, key=f"sugestao_{texto}", on_click=sugerir, args=(texto,))
    if not com_agente:
        st.info("Sem a chave da OpenAI você pode listar peças, comparar ofertas e executar /t24. "
                "As políticas, o CEP e as perguntas abertas precisam do agente.",
                title="Modo local", icon=":material/info:")
if pergunta:
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        rastro = Rastro()
        rastro.eventos = PassosAoVivo()
        saida = None
        with st.status(":shimmer[Consultando e verificando]", type="compact") as estado:
            llm, classificador, indice = preparar_agente(e_diagnostico_t24(pergunta))
            fluxo = criar_fluxo(cenario, MEMORIA, llm=llm, classificador=classificador,
                                indice=indice, rastro=rastro)
            try:
                saida = fluxo.invoke({"input": pergunta}, config={"configurable": {
                    "user_id": USUARIO, "session_id": st.session_state.sessao}})
            except Exception as exc:
                estado.update(label=f"Consulta não concluída: {type(exc).__name__}", state="error")
            else:
                passos = rastro.eventos.passos
                estado.update(state="complete", label=(
                    f"Como cheguei a esta resposta · {len(passos)} passos" if passos
                    else "Respondi com as regras do catálogo, sem chamar o modelo"))
                if passos:
                    st.session_state.passos[(st.session_state.sessao, len(mensagens) + 1)] = passos
        if saida is not None:
            mostrar_mensagem(saida)
