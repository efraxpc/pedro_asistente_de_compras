import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from langchain_core.embeddings import Embeddings

from pedro.agent import Traza, crear_flujo, herramientas, renderizar
from pedro.catalog import crear_escenario
from pedro.contracts import Evidencia, RespuestaCompra, Solicitud
from pedro.policy_demo import (PREGUNTA_T24_ORIGINAL, crear_indice_demo,
                               fragmentos_demo, huella_corpus,
                               reescribir_consulta_entrega)
from pedro.rag import consultar
from pedro.verification import verificar
from pedro.memory import Historial, guardar_borrador, nueva_sesion


class EmbeddingsPrueba(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(texto) for texto in texts]

    def embed_query(self, text: str) -> list[float]:
        texto = text.lower()
        return [float("devolucion" in texto), float("garantia" in texto),
                float("entrega" in texto)]


def _corpus_prueba(carpeta: Path) -> None:
    for nombre, palabra in (("devoluciones", "devolucion"),
                            ("garantia", "garantia"), ("entrega", "entrega")):
        (carpeta / f"{nombre}.md").write_text(
            f"# DEMOSTRACIÓN T15\n\n**Versión:** 1.1\n\ncorpus sintético\n\n## Regla\n{palabra} "
            f"{palabra} exclusiva para {nombre}.\n", encoding="utf-8")


def test_corpus_extenso_se_fragmenta_con_fuentes_estables():
    documentos = fragmentos_demo()
    assert len(documentos) >= 18
    assert len({doc.id for doc in documentos}) == len(documentos)
    assert all(len(doc.page_content) <= 700 for doc in documentos)
    for tema in ("devoluciones", "garantia", "entrega"):
        fragmentos = [doc for doc in documentos if doc.metadata["tema"] == tema]
        assert len(fragmentos) >= 6
        assert all(doc.metadata["origen"] == "ficticio_demo" for doc in fragmentos)
        assert all(doc.metadata["id"] == doc.id for doc in fragmentos)
        assert all(doc.metadata["version"] == "1.1" for doc in fragmentos)
        por_seccion = Counter(doc.metadata["seccion"] for doc in fragmentos)
        assert all(cantidad >= 2 for seccion, cantidad in por_seccion.items()
                   if seccion[0].isdigit())


def test_faiss_local_filtra_y_conserva_citas(tmp_path):
    _corpus_prueba(tmp_path)
    indice = crear_indice_demo(tmp_path, EmbeddingsPrueba())
    assert not (tmp_path / "index.pkl").exists()
    assert indice.index.ntotal == len(fragmentos_demo(tmp_path))
    huella_anterior = huella_corpus(tmp_path)
    with (tmp_path / "garantia.md").open("a", encoding="utf-8") as archivo:
        archivo.write("\nNueva versión ficticia.\n")
    assert huella_corpus(tmp_path) != huella_anterior
    resultados = consultar(indice, "garantia", k=2, filtro={"tema": "garantia"},
                           fetch_k=indice.index.ntotal)
    assert len(resultados) == 2
    assert all(r["metadatos"]["tema"] == "garantia" for r in resultados)
    assert all(indice.docstore.search(r["fuente_id"]).page_content == r["texto"]
               for r in resultados)
    assert consultar(indice, "garantia", filtro={"tema": "inexistente"},
                     fetch_k=indice.index.ntotal) == []

    escenario = crear_escenario(tmp_path / "catalogos")
    respuesta = RespuestaCompra(
        estado="politica", dataset_id=escenario.dataset_id, solicitud=Solicitud(),
        mensaje="garantia exclusiva para garantia.",
        evidencias=[Evidencia(tipo="politica", fuente_id=resultados[0]["fuente_id"],
                             texto=resultados[0]["texto"])],
    )
    assert verificar(respuesta, escenario, indice=indice) == []
    assert renderizar(respuesta, indice=indice).startswith("Política ficticia de demostración.")
    herramienta = next(h for h in herramientas(escenario, tmp_path / "memoria.sqlite3",
                                       "ana", "consulta garantia", indice)
                       if h.name == "consultar_politicas")
    assert "ficticio_demo" in herramienta.invoke({"pregunta": "garantia"})


def test_chat_publica_politica_ficticia_con_fuente(tmp_path, monkeypatch):
    import pedro.agent as modulo

    _corpus_prueba(tmp_path)
    indice = crear_indice_demo(tmp_path, EmbeddingsPrueba())
    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    herramienta = next(h for h in herramientas(escenario, memoria, "ana",
                                       "consulta devolucion", indice)
                       if h.name == "consultar_politicas")
    observacion = herramienta.invoke({"pregunta": "devolucion"})
    fragmento = json.loads(observacion)["fragmentos"][0]
    respuesta = RespuestaCompra(
        estado="politica", dataset_id=escenario.dataset_id, solicitud=Solicitud(),
        mensaje="La devolución del corpus es ficticia.",
        evidencias=[Evidencia(tipo="politica", fuente_id=fragmento["fuente_id"],
                             texto=fragmento["texto"])],
    )

    class Executor:
        def invoke(self, entrada, config):
            return {"output": respuesta.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_politicas"), observacion)]}

    class NLI:
        def clasificar(self, premisa, hipotesis):
            return "entailment"

    monkeypatch.setattr(modulo, "crear_agente", lambda *args, **kwargs: Executor())
    flujo = crear_flujo(escenario, memoria, llm=object(), clasificador=NLI(), indice=indice)
    salida = flujo.invoke({"input": "¿Qué dice la política de devolución?"},
                         config={"configurable": {"user_id": "ana", "session_id": sesion}})
    assert "Política ficticia de demostración." in salida.content
    assert fragmento["fuente_id"] in salida.content
    assert [m.type for m in Historial(memoria, "ana", sesion).todos()] == ["human", "ai"]


def test_pregunta_natural_reescribe_recupera_y_publica_traza(tmp_path, monkeypatch):
    import pedro.agent as modulo

    assert reescribir_consulta_entrega(PREGUNTA_T24_ORIGINAL) is not None
    assert reescribir_consulta_entrega("¿Puedo devolver varias cajas?") is None
    indice = crear_indice_demo()
    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    herramienta = next(h for h in herramientas(escenario, memoria, "ana",
                                       PREGUNTA_T24_ORIGINAL, indice)
                       if h.name == "consultar_politicas")
    observacion = herramienta.invoke({"pregunta": PREGUNTA_T24_ORIGINAL})
    dato = json.loads(observacion)
    assert dato["diagnostico"]["correccion_observada"] is True
    assert dato["diagnostico"]["posicion_antes"] is None
    assert dato["diagnostico"]["posicion_despues"] == 1
    fragmento = dato["fragmentos"][0]
    respuesta = RespuestaCompra(
        estado="politica", dataset_id=escenario.dataset_id, solicitud=Solicitud(),
        mensaje="Una entrega parcial solo puede describirse si hay un acuerdo simulado explícito.",
        evidencias=[Evidencia(tipo="politica", fuente_id=fragmento["fuente_id"],
                             texto=fragmento["texto"])],
    )
    assert "política sin recuperación observada" in verificar(
        respuesta, escenario, indice=indice, observaciones=[])

    class Executor:
        def invoke(self, entrada, config):
            raise AssertionError("la ruta estable de entrega no debe depender del LLM")

    class NLI:
        def clasificar(self, premisa, hipotesis):
            return "entailment"

    monkeypatch.setattr(modulo, "crear_agente", lambda *args, **kwargs: Executor())
    guardar_borrador(memoria, "ana", sesion, {"solicitud": {"producto_id": "PEC-01-0001"},
                                           "esperando": "cantidad"})
    traza = Traza()
    flujo = crear_flujo(escenario, memoria, llm=object(), clasificador=NLI(),
                       indice=indice, traza=traza)
    salida = flujo.invoke({"input": PREGUNTA_T24_ORIGINAL},
                         config={"configurable": {"user_id": "ana", "session_id": sesion}})
    repetida = flujo.invoke({"input": PREGUNTA_T24_ORIGINAL},
                           config={"configurable": {"user_id": "ana", "session_id": sesion}})
    assert "Política ficticia de demostración." in salida.content
    assert "Recuperación T24" in salida.content
    assert "fuera del top-4" in salida.content
    assert "posición 1" in salida.content
    assert repetida.content == salida.content
    assert [e.get("herramienta") for e in traza.eventos
            if e["evento"] == "tool_start"] == ["consultar_politicas"] * 2
