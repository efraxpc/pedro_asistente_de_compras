"""Preferencias e historial persistentes, separados del catálogo."""
import json
import hashlib
import math
import re
import sqlite3
import uuid
from pathlib import Path

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict


def preparar_memoria(ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ruta) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS preferencias (
          user_id TEXT NOT NULL, clave TEXT NOT NULL, valor TEXT NOT NULL,
          PRIMARY KEY(user_id,clave));
        CREATE TABLE IF NOT EXISTS sesiones (
          session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, dataset_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS turnos (
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
          rol TEXT NOT NULL CHECK(rol IN ('user','assistant')), contenido TEXT NOT NULL,
          FOREIGN KEY(session_id) REFERENCES sesiones(session_id));
        CREATE TABLE IF NOT EXISTS mensajes_lc (
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
          mensaje TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sesiones(session_id));
        CREATE TABLE IF NOT EXISTS episodios (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
          session_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
          texto TEXT NOT NULL, vector TEXT NOT NULL,
          FOREIGN KEY(session_id) REFERENCES sesiones(session_id));
        CREATE INDEX IF NOT EXISTS idx_episodios_usuario ON episodios(user_id,id);
        """)


def nueva_sesion(ruta: Path, user_id: str, dataset_id: str) -> str:
    preparar_memoria(ruta)
    session_id = str(uuid.uuid4())
    with sqlite3.connect(ruta) as db:
        db.execute("INSERT INTO sesiones VALUES (?,?,?)", (session_id, user_id, dataset_id))
    return session_id


def listar_sesiones(ruta: Path, user_id: str) -> list[dict[str, str]]:
    """Return this user's chats, most recently active first."""
    preparar_memoria(ruta)
    with sqlite3.connect(ruta) as db:
        sesiones = db.execute("""
            SELECT s.session_id, s.dataset_id
            FROM sesiones AS s
            LEFT JOIN mensajes_lc AS m ON m.session_id = s.session_id
            WHERE s.user_id = ?
            GROUP BY s.rowid
            ORDER BY COALESCE(MAX(m.id), 0) DESC, s.rowid DESC
        """, (user_id,)).fetchall()
        resultado = []
        for session_id, dataset_id in sesiones:
            fila = db.execute("SELECT mensaje FROM mensajes_lc WHERE session_id=? "
                              "ORDER BY id LIMIT 1", (session_id,)).fetchone()
            titulo = "Nuevo chat"
            if fila:
                contenido = json.loads(fila[0]).get("data", {}).get("content", "")
                if isinstance(contenido, str) and contenido.strip():
                    titulo = contenido.strip().replace("\n", " ")[:48]
            resultado.append({"session_id": session_id, "dataset_id": dataset_id,
                              "titulo": titulo})
    return resultado


def mensajes_sesion(ruta: Path, session_id: str, user_id: str) -> list[BaseMessage]:
    """Read the full UI history without changing the agent's 12-message window."""
    HistorialSQLite(ruta, session_id, user_id)
    with sqlite3.connect(ruta) as db:
        filas = db.execute("SELECT mensaje FROM mensajes_lc WHERE session_id=? ORDER BY id",
                           (session_id,)).fetchall()
    return messages_from_dict([json.loads(fila[0]) for fila in filas])


def guardar_preferencia(ruta: Path, user_id: str, clave: str, valor: str,
                        *, explicita: bool) -> None:
    if not explicita or not clave.strip() or not valor.strip():
        raise ValueError("la preferencia debe ser explícita y no vacía")
    preparar_memoria(ruta)
    with sqlite3.connect(ruta) as db:
        db.execute("INSERT INTO preferencias VALUES (?,?,?) ON CONFLICT(user_id,clave) "
                   "DO UPDATE SET valor=excluded.valor", (user_id, clave, valor))


def preferencias(ruta: Path, user_id: str) -> dict[str, str]:
    preparar_memoria(ruta)
    with sqlite3.connect(ruta) as db:
        return dict(db.execute("SELECT clave, valor FROM preferencias WHERE user_id=?", (user_id,)))


def agregar_turno(ruta: Path, session_id: str, rol: str, contenido: str) -> None:
    if rol not in ("user", "assistant"):
        raise ValueError("rol inválido")
    preparar_memoria(ruta)
    with sqlite3.connect(ruta) as db:
        db.execute("INSERT INTO turnos(session_id,rol,contenido) VALUES (?,?,?)",
                   (session_id, rol, contenido))


def historial(ruta: Path, session_id: str, limite: int = 12) -> list[dict[str, str]]:
    preparar_memoria(ruta)
    with sqlite3.connect(ruta) as db:
        filas = db.execute("SELECT rol,contenido FROM (SELECT id,rol,contenido FROM turnos "
                           "WHERE session_id=? ORDER BY id DESC LIMIT ?) ORDER BY id",
                           (session_id, limite)).fetchall()
    return [{"rol": rol, "contenido": contenido} for rol, contenido in filas]


class HistorialSQLite(BaseChatMessageHistory):
    """Adaptador persistente para RunnableWithMessageHistory."""

    def __init__(self, ruta: Path, session_id: str, user_id: str):
        preparar_memoria(ruta)
        with sqlite3.connect(ruta) as db:
            fila = db.execute("SELECT user_id FROM sesiones WHERE session_id=?", (session_id,)).fetchone()
        if fila is None or fila[0] != user_id:
            raise ValueError("sesión inexistente o de otro usuario")
        self.ruta, self.session_id = ruta, session_id

    @property
    def messages(self) -> list[BaseMessage]:
        with sqlite3.connect(self.ruta) as db:
            filas = db.execute("SELECT mensaje FROM (SELECT id,mensaje FROM mensajes_lc "
                               "WHERE session_id=? ORDER BY id DESC LIMIT 12) ORDER BY id",
                               (self.session_id,)).fetchall()
        return messages_from_dict([json.loads(f[0]) for f in filas])

    def add_messages(self, messages: list[BaseMessage]) -> None:
        with sqlite3.connect(self.ruta) as db:
            db.executemany("INSERT INTO mensajes_lc(session_id,mensaje) VALUES (?,?)",
                           [(self.session_id, json.dumps(d, ensure_ascii=False))
                            for d in messages_to_dict(messages)])

    def clear(self) -> None:
        with sqlite3.connect(self.ruta) as db:
            db.execute("DELETE FROM mensajes_lc WHERE session_id=?", (self.session_id,))


def vector_demo(texto: str, dimension: int = 128) -> list[float]:
    """Embedding determinista para pruebas offline; no acredita calidad semántica."""
    valores = [0.0] * dimension
    for token in re.findall(r"\w+", texto.lower()):
        indice = int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], "big") % dimension
        valores[indice] += 1.0
    norma = math.sqrt(sum(v * v for v in valores)) or 1.0
    return [v / norma for v in valores]


def guardar_episodio(ruta: Path, user_id: str, session_id: str, dataset_id: str,
                     texto: str, *, embed=vector_demo) -> int:
    if not texto.strip():
        raise ValueError("episodio vacío")
    preparar_memoria(ruta)
    with sqlite3.connect(ruta) as db:
        sesion = db.execute("SELECT user_id,dataset_id FROM sesiones WHERE session_id=?",
                            (session_id,)).fetchone()
        if sesion != (user_id, dataset_id):
            raise ValueError("identidad de episodio incompatible")
        cursor = db.execute("INSERT INTO episodios(user_id,session_id,dataset_id,texto,vector) "
                            "VALUES (?,?,?,?,?)",
                            (user_id, session_id, dataset_id, texto, json.dumps(embed(texto))))
        return cursor.lastrowid


def recuperar_episodios(ruta: Path, user_id: str, consulta: str, *, k: int = 3,
                        embed=vector_demo) -> list[dict]:
    preparar_memoria(ruta)
    vector = embed(consulta)
    with sqlite3.connect(ruta) as db:
        filas = db.execute("SELECT id,session_id,dataset_id,texto,vector FROM episodios "
                           "WHERE user_id=?", (user_id,)).fetchall()
    resultados = []
    for id_, session_id, dataset_id, texto, serializado in filas:
        otro = json.loads(serializado)
        if len(otro) != len(vector):
            continue
        puntuacion = sum(a*b for a,b in zip(vector, otro))
        resultados.append({"id": id_, "session_id": session_id, "dataset_id": dataset_id,
                           "texto": texto, "similitud": puntuacion})
    return sorted(resultados, key=lambda r: (-r["similitud"], r["id"]))[:max(0, min(k, 20))]
