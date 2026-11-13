"""Histórico e lembranças isolados por usuário, sessão e cenário."""
import json
import math
import sqlite3
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Protocol, Sequence

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

MODELO_LEMBRANCAS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
JANELA_MENSAGENS = 12
VERSAO_LEMBRANCAS = "fastembed-0.9.1"


class Embedder(Protocol):
    modelo: str
    versao: str

    def embed(self, texto: str) -> list[float]: ...


class FastEmbedder:
    modelo = MODELO_LEMBRANCAS
    versao = VERSAO_LEMBRANCAS

    def __init__(self):
        self._modelo = _modelo_fastembed()

    def embed(self, texto: str) -> list[float]:
        return list(next(iter(self._modelo.embed([texto]))).astype(float))


@lru_cache(maxsize=1)
def _modelo_fastembed():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODELO_LEMBRANCAS)


def preparar(caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(caminho) as db:
        db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS sessoes (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
          criada TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS mensagens (
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
          dado TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sessoes(id));
        CREATE TABLE IF NOT EXISTS preferencias (
          user_id TEXT NOT NULL, chave TEXT NOT NULL, valor TEXT NOT NULL,
          PRIMARY KEY(user_id,chave));
        CREATE TABLE IF NOT EXISTS episodios (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
          session_id TEXT NOT NULL, dataset_id TEXT NOT NULL, texto TEXT NOT NULL,
          vetor TEXT NOT NULL, modelo TEXT NOT NULL, versao TEXT NOT NULL,
          FOREIGN KEY(session_id) REFERENCES sessoes(id));
        CREATE TABLE IF NOT EXISTS rascunhos (
          session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
          dado TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sessoes(id));
        CREATE INDEX IF NOT EXISTS episodios_usuario ON episodios(user_id,id);
        """)


def nova_sessao(caminho: Path, user_id: str, dataset_id: str) -> str:
    preparar(caminho)
    session_id = str(uuid.uuid4())
    with sqlite3.connect(caminho) as db:
        db.execute("INSERT INTO sessoes(id,user_id,dataset_id) VALUES (?,?,?)",
                   (session_id, user_id, dataset_id))
    return session_id


def sessoes(caminho: Path, user_id: str) -> list[dict]:
    preparar(caminho)
    with sqlite3.connect(caminho) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(
            "SELECT id,dataset_id FROM sessoes WHERE user_id=? ORDER BY criada DESC,id DESC", (user_id,))]


def apagar_sessao(caminho: Path, user_id: str, session_id: str) -> None:
    """Apaga uma conversa do usuário com tudo o que saiu dela.

    Vão embora as mensagens, o rascunho de compra e os episódios (lembranças) dessa conversa.
    As preferências são do usuário, não da conversa, e ficam.
    """
    preparar(caminho)
    with sqlite3.connect(caminho) as db:
        if db.execute("SELECT 1 FROM sessoes WHERE id=? AND user_id=?",
                      (session_id, user_id)).fetchone() is None:
            raise ValueError("sessão alheia ou inexistente")
        for tabela in ("mensagens", "rascunhos", "episodios"):
            db.execute(f"DELETE FROM {tabela} WHERE session_id=?", (session_id,))
        db.execute("DELETE FROM sessoes WHERE id=? AND user_id=?", (session_id, user_id))


def apagar_sessoes(caminho: Path, user_id: str) -> int:
    """Apaga todas as conversas do usuário e devolve quantas eram. As preferências ficam."""
    todas = sessoes(caminho, user_id)
    for sessao in todas:
        apagar_sessao(caminho, user_id, sessao["id"])
    return len(todas)


def dataset_sessao(caminho: Path, user_id: str, session_id: str) -> str:
    preparar(caminho)
    with sqlite3.connect(caminho) as db:
        linha = db.execute("SELECT dataset_id FROM sessoes WHERE id=? AND user_id=?",
                           (session_id, user_id)).fetchone()
    if linha is None:
        raise ValueError("sessão alheia ou inexistente")
    return linha[0]


def ler_rascunho(caminho: Path, user_id: str, session_id: str) -> dict | None:
    dataset_id = dataset_sessao(caminho, user_id, session_id)
    with sqlite3.connect(caminho) as db:
        linha = db.execute("SELECT dado FROM rascunhos WHERE session_id=? AND user_id=? "
                           "AND dataset_id=?", (session_id, user_id, dataset_id)).fetchone()
    return json.loads(linha[0]) if linha else None


def salvar_rascunho(caminho: Path, user_id: str, session_id: str, dado: dict) -> None:
    dataset_id = dataset_sessao(caminho, user_id, session_id)
    with sqlite3.connect(caminho) as db:
        db.execute("INSERT INTO rascunhos(session_id,user_id,dataset_id,dado) VALUES (?,?,?,?) "
                   "ON CONFLICT(session_id) DO UPDATE SET dado=excluded.dado, "
                   "user_id=excluded.user_id,dataset_id=excluded.dataset_id",
                   (session_id, user_id, dataset_id, json.dumps(dado, ensure_ascii=False)))


class Historico(BaseChatMessageHistory):
    def __init__(self, caminho: Path, user_id: str, session_id: str):
        dataset_sessao(caminho, user_id, session_id)
        self.caminho, self.session_id = caminho, session_id

    @property
    def messages(self) -> list[BaseMessage]:
        with sqlite3.connect(self.caminho) as db:
            linhas = db.execute("SELECT dado FROM (SELECT id,dado FROM mensagens WHERE session_id=? "
                                "ORDER BY id DESC LIMIT ?) ORDER BY id",
                                (self.session_id, JANELA_MENSAGENS))
            return messages_from_dict([json.loads(f[0]) for f in linhas])

    @messages.setter
    def messages(self, value: list[BaseMessage]) -> None:
        self.clear()
        self.add_messages(value)

    def todos(self) -> list[BaseMessage]:
        with sqlite3.connect(self.caminho) as db:
            linhas = db.execute("SELECT dado FROM mensagens WHERE session_id=? ORDER BY id", (self.session_id,))
            return messages_from_dict([json.loads(f[0]) for f in linhas])

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        with sqlite3.connect(self.caminho) as db:
            db.executemany("INSERT INTO mensagens(session_id,dado) VALUES (?,?)",
                           [(self.session_id, json.dumps(d, ensure_ascii=False))
                            for d in messages_to_dict(messages)])

    def clear(self) -> None:
        with sqlite3.connect(self.caminho) as db:
            db.execute("DELETE FROM mensagens WHERE session_id=?", (self.session_id,))


def salvar_preferencia(caminho: Path, user_id: str, chave: str, valor: str, *, explicita: bool) -> None:
    if not explicita or not chave.strip() or not valor.strip():
        raise ValueError("preferência não explícita")
    preparar(caminho)
    with sqlite3.connect(caminho) as db:
        db.execute("INSERT INTO preferencias VALUES (?,?,?) ON CONFLICT(user_id,chave) "
                   "DO UPDATE SET valor=excluded.valor", (user_id, chave, valor))


def preferencias(caminho: Path, user_id: str) -> dict[str, str]:
    preparar(caminho)
    with sqlite3.connect(caminho) as db:
        return dict(db.execute("SELECT chave,valor FROM preferencias WHERE user_id=?", (user_id,)))


def tem_episodios(caminho: Path, user_id: str) -> bool:
    preparar(caminho)
    with sqlite3.connect(caminho) as db:
        return db.execute("SELECT 1 FROM episodios WHERE user_id=? LIMIT 1", (user_id,)).fetchone() is not None


def salvar_episodio(caminho: Path, user_id: str, session_id: str, texto: str,
                    embedder: Embedder) -> int:
    dataset_id = dataset_sessao(caminho, user_id, session_id)
    vetor = embedder.embed("passage: " + texto)
    with sqlite3.connect(caminho) as db:
        cursor = db.execute("INSERT INTO episodios(user_id,session_id,dataset_id,texto,vetor,modelo,versao) "
                            "VALUES (?,?,?,?,?,?,?)", (user_id, session_id, dataset_id, texto,
                            json.dumps(vetor), embedder.modelo, embedder.versao))
        if cursor.lastrowid is None:
            raise RuntimeError("o episódio não foi salvo")
        return cursor.lastrowid


def atualizar_episodio(caminho: Path, user_id: str, episodio_id: int, texto: str,
                       embedder: Embedder) -> None:
    vetor = embedder.embed("passage: " + texto)
    with sqlite3.connect(caminho) as db:
        cursor = db.execute("UPDATE episodios SET texto=?,vetor=?,modelo=?,versao=? "
                            "WHERE id=? AND user_id=?", (texto, json.dumps(vetor), embedder.modelo,
                            embedder.versao, episodio_id, user_id))
        if cursor.rowcount != 1:
            raise ValueError("episódio alheio ou inexistente")


def recuperar(caminho: Path, user_id: str, pergunta: str, embedder: Embedder, k: int = 3) -> list[dict]:
    preparar(caminho)
    consulta = embedder.embed("query: " + pergunta)
    with sqlite3.connect(caminho) as db:
        linhas = db.execute("SELECT id,dataset_id,texto,vetor FROM episodios WHERE user_id=? "
                            "AND modelo=? AND versao=?", (user_id, embedder.modelo, embedder.versao))
        candidatos = []
        for eid, dataset_id, texto, vetor_json in linhas:
            vetor = json.loads(vetor_json)
            if len(vetor) != len(consulta):
                continue
            produto = sum(a*b for a,b in zip(consulta, vetor))
            norma = math.sqrt(sum(a*a for a in consulta) * sum(b*b for b in vetor)) or 1
            candidatos.append({"id": eid, "dataset_id": dataset_id, "texto": texto,
                               "similaridade": produto / norma})
    return sorted(candidatos, key=lambda x: (-x["similaridade"], x["id"]))[:k]


def mapa_memorias(caminho: Path, user_id: str, session_id: str) -> dict:
    """O que está guardado em cada tipo de memória (taxonomia CoALA) para um usuário e uma sessão."""
    preparar(caminho)
    historico = Historico(caminho, user_id, session_id)
    rascunho = ler_rascunho(caminho, user_id, session_id)
    with sqlite3.connect(caminho) as db:
        episodios = db.execute("SELECT COUNT(*), COUNT(DISTINCT session_id) FROM episodios "
                               "WHERE user_id=?", (user_id,)).fetchone()
    return {
        "trabalho (curto prazo, por sessão)": {
            "rascunho_de_compra": {k: v for k, v in (rascunho or {}).get("solicitacao", {}).items()
                                   if v is not None},
            "mensagens_na_janela": len(historico.messages),
            "mensagens_salvas": len(historico.todos())},
        "episódica (longo prazo, por usuário)": {
            "episodios": episodios[0], "sessoes_de_origem": episodios[1],
            "recuperacao": "similaridade de cosseno, top 3, modelo " + MODELO_LEMBRANCAS},
        "semântica (longo prazo)": {
            "preferencias_do_usuario": preferencias(caminho, user_id),
            "conhecimento_do_dominio": "catálogo SQLite do cenário e políticas em FAISS"},
        "procedimental (longo prazo)": {
            "onde": "prompt PTCF, exemplos few-shot, regras de diálogo e código de verificação",
            "muda": "somente com uma nova versão do projeto"},
    }
