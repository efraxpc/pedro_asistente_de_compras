"""Historial y recuerdos aislados por usuario, sesión y escenario."""
import json
import math
import sqlite3
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Protocol, Sequence

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

MODELO_RECUERDOS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VENTANA_MENSAJES = 12
VERSION_RECUERDOS = "fastembed-0.9.1"


class Embedder(Protocol):
    modelo: str
    version: str

    def embed(self, texto: str) -> list[float]: ...


class FastEmbedder:
    modelo = MODELO_RECUERDOS
    version = VERSION_RECUERDOS

    def __init__(self):
        self._modelo = _modelo_fastembed()

    def embed(self, texto: str) -> list[float]:
        return list(next(iter(self._modelo.embed([texto]))).astype(float))


@lru_cache(maxsize=1)
def _modelo_fastembed():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODELO_RECUERDOS)


def preparar(ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ruta) as db:
        db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS sesiones (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
          creada TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS mensajes (
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
          dato TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sesiones(id));
        CREATE TABLE IF NOT EXISTS preferencias (
          user_id TEXT NOT NULL, clave TEXT NOT NULL, valor TEXT NOT NULL,
          PRIMARY KEY(user_id,clave));
        CREATE TABLE IF NOT EXISTS episodios (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
          session_id TEXT NOT NULL, dataset_id TEXT NOT NULL, texto TEXT NOT NULL,
          vector TEXT NOT NULL, modelo TEXT NOT NULL, version TEXT NOT NULL,
          FOREIGN KEY(session_id) REFERENCES sesiones(id));
        CREATE TABLE IF NOT EXISTS borradores (
          session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
          dato TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sesiones(id));
        CREATE INDEX IF NOT EXISTS episodios_usuario ON episodios(user_id,id);
        """)


def nueva_sesion(ruta: Path, user_id: str, dataset_id: str) -> str:
    preparar(ruta)
    session_id = str(uuid.uuid4())
    with sqlite3.connect(ruta) as db:
        db.execute("INSERT INTO sesiones(id,user_id,dataset_id) VALUES (?,?,?)",
                   (session_id, user_id, dataset_id))
    return session_id


def sesiones(ruta: Path, user_id: str) -> list[dict]:
    preparar(ruta)
    with sqlite3.connect(ruta) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(
            "SELECT id,dataset_id FROM sesiones WHERE user_id=? ORDER BY creada DESC,id DESC", (user_id,))]


def dataset_sesion(ruta: Path, user_id: str, session_id: str) -> str:
    preparar(ruta)
    with sqlite3.connect(ruta) as db:
        fila = db.execute("SELECT dataset_id FROM sesiones WHERE id=? AND user_id=?",
                          (session_id, user_id)).fetchone()
    if fila is None:
        raise ValueError("sesión ajena o inexistente")
    return fila[0]


def leer_borrador(ruta: Path, user_id: str, session_id: str) -> dict | None:
    dataset_id = dataset_sesion(ruta, user_id, session_id)
    with sqlite3.connect(ruta) as db:
        fila = db.execute("SELECT dato FROM borradores WHERE session_id=? AND user_id=? "
                          "AND dataset_id=?", (session_id, user_id, dataset_id)).fetchone()
    return json.loads(fila[0]) if fila else None


def guardar_borrador(ruta: Path, user_id: str, session_id: str, dato: dict) -> None:
    dataset_id = dataset_sesion(ruta, user_id, session_id)
    with sqlite3.connect(ruta) as db:
        db.execute("INSERT INTO borradores(session_id,user_id,dataset_id,dato) VALUES (?,?,?,?) "
                   "ON CONFLICT(session_id) DO UPDATE SET dato=excluded.dato, "
                   "user_id=excluded.user_id,dataset_id=excluded.dataset_id",
                   (session_id, user_id, dataset_id, json.dumps(dato, ensure_ascii=False)))


class Historial(BaseChatMessageHistory):
    def __init__(self, ruta: Path, user_id: str, session_id: str):
        dataset_sesion(ruta, user_id, session_id)
        self.ruta, self.session_id = ruta, session_id

    @property
    def messages(self) -> list[BaseMessage]:
        with sqlite3.connect(self.ruta) as db:
            filas = db.execute("SELECT dato FROM (SELECT id,dato FROM mensajes WHERE session_id=? "
                               "ORDER BY id DESC LIMIT ?) ORDER BY id",
                               (self.session_id, VENTANA_MENSAJES))
            return messages_from_dict([json.loads(f[0]) for f in filas])

    @messages.setter
    def messages(self, value: list[BaseMessage]) -> None:
        self.clear()
        self.add_messages(value)

    def todos(self) -> list[BaseMessage]:
        with sqlite3.connect(self.ruta) as db:
            filas = db.execute("SELECT dato FROM mensajes WHERE session_id=? ORDER BY id", (self.session_id,))
            return messages_from_dict([json.loads(f[0]) for f in filas])

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        with sqlite3.connect(self.ruta) as db:
            db.executemany("INSERT INTO mensajes(session_id,dato) VALUES (?,?)",
                           [(self.session_id, json.dumps(d, ensure_ascii=False))
                            for d in messages_to_dict(messages)])

    def clear(self) -> None:
        with sqlite3.connect(self.ruta) as db:
            db.execute("DELETE FROM mensajes WHERE session_id=?", (self.session_id,))


def guardar_preferencia(ruta: Path, user_id: str, clave: str, valor: str, *, explicita: bool) -> None:
    if not explicita or not clave.strip() or not valor.strip():
        raise ValueError("preferencia no explícita")
    preparar(ruta)
    with sqlite3.connect(ruta) as db:
        db.execute("INSERT INTO preferencias VALUES (?,?,?) ON CONFLICT(user_id,clave) "
                   "DO UPDATE SET valor=excluded.valor", (user_id, clave, valor))


def preferencias(ruta: Path, user_id: str) -> dict[str, str]:
    preparar(ruta)
    with sqlite3.connect(ruta) as db:
        return dict(db.execute("SELECT clave,valor FROM preferencias WHERE user_id=?", (user_id,)))


def tiene_episodios(ruta: Path, user_id: str) -> bool:
    preparar(ruta)
    with sqlite3.connect(ruta) as db:
        return db.execute("SELECT 1 FROM episodios WHERE user_id=? LIMIT 1", (user_id,)).fetchone() is not None


def guardar_episodio(ruta: Path, user_id: str, session_id: str, texto: str,
                     embedder: Embedder) -> int:
    dataset_id = dataset_sesion(ruta, user_id, session_id)
    vector = embedder.embed("passage: " + texto)
    with sqlite3.connect(ruta) as db:
        cursor = db.execute("INSERT INTO episodios(user_id,session_id,dataset_id,texto,vector,modelo,version) "
                            "VALUES (?,?,?,?,?,?,?)", (user_id, session_id, dataset_id, texto,
                            json.dumps(vector), embedder.modelo, embedder.version))
        if cursor.lastrowid is None:
            raise RuntimeError("no se guardó el episodio")
        return cursor.lastrowid


def actualizar_episodio(ruta: Path, user_id: str, episodio_id: int, texto: str,
                        embedder: Embedder) -> None:
    vector = embedder.embed("passage: " + texto)
    with sqlite3.connect(ruta) as db:
        cursor = db.execute("UPDATE episodios SET texto=?,vector=?,modelo=?,version=? "
                            "WHERE id=? AND user_id=?", (texto, json.dumps(vector), embedder.modelo,
                            embedder.version, episodio_id, user_id))
        if cursor.rowcount != 1:
            raise ValueError("episodio ajeno o inexistente")


def recuperar(ruta: Path, user_id: str, pregunta: str, embedder: Embedder, k: int = 3) -> list[dict]:
    preparar(ruta)
    consulta = embedder.embed("query: " + pregunta)
    with sqlite3.connect(ruta) as db:
        filas = db.execute("SELECT id,dataset_id,texto,vector FROM episodios WHERE user_id=? "
                           "AND modelo=? AND version=?", (user_id, embedder.modelo, embedder.version))
        candidatos = []
        for eid, dataset_id, texto, vector_json in filas:
            vector = json.loads(vector_json)
            if len(vector) != len(consulta):
                continue
            producto = sum(a*b for a,b in zip(consulta, vector))
            norma = math.sqrt(sum(a*a for a in consulta) * sum(b*b for b in vector)) or 1
            candidatos.append({"id": eid, "dataset_id": dataset_id, "texto": texto,
                               "similitud": producto / norma})
    return sorted(candidatos, key=lambda x: (-x["similitud"], x["id"]))[:k]


def mapa_memorias(ruta: Path, user_id: str, session_id: str) -> dict:
    """Qué hay guardado en cada tipo de memoria (taxonomía CoALA) para un usuario y una sesión."""
    preparar(ruta)
    historial = Historial(ruta, user_id, session_id)
    borrador = leer_borrador(ruta, user_id, session_id)
    with sqlite3.connect(ruta) as db:
        episodios = db.execute("SELECT COUNT(*), COUNT(DISTINCT session_id) FROM episodios "
                               "WHERE user_id=?", (user_id,)).fetchone()
    return {
        "trabajo (corto plazo, por sesión)": {
            "borrador_de_compra": {k: v for k, v in (borrador or {}).get("solicitud", {}).items()
                                   if v is not None},
            "mensajes_en_la_ventana": len(historial.messages),
            "mensajes_guardados": len(historial.todos())},
        "episódica (largo plazo, por usuario)": {
            "episodios": episodios[0], "sesiones_de_origen": episodios[1],
            "recuperación": "similitud coseno, top 3, modelo " + MODELO_RECUERDOS},
        "semántica (largo plazo)": {
            "preferencias_del_usuario": preferencias(ruta, user_id),
            "conocimiento_del_dominio": "catálogo SQLite del escenario y políticas en FAISS"},
        "procedimental (largo plazo)": {
            "donde": "prompt PTCF, ejemplos few-shot, reglas de diálogo y código de verificación",
            "cambia": "solo con una nueva versión del proyecto"},
    }
