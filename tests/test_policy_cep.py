from types import SimpleNamespace

from langchain_core.documents import Document

from pedro.catalog import crear_escenario
from pedro.contracts import Evidencia, RespuestaCompra, Solicitud
from pedro.nli import verificar_nli
from pedro.verification import verificar
from pedro.memory import Historial, nueva_sesion
from pedro.agent import crear_flujo


def test_cep_exige_observacion_coincidente(tmp_path):
    escenario = crear_escenario(tmp_path)
    respuesta = RespuestaCompra(estado="cep", dataset_id=escenario.dataset_id,
        solicitud=Solicitud(cep="01001000"), cidade="São Paulo", uf="SP", modo_cep="real",
        evidencias=[Evidencia(tipo="viacep", fuente_id="ViaCEP:01001000", texto="São Paulo/SP")])
    observacion = ("consultar_cep", {"estado": "ok", "cep": "01001000",
                                    "cidade": "São Paulo", "uf": "SP", "modo": "real"})
    assert verificar(respuesta, escenario, observaciones=[observacion]) == []
    assert "ubicación no coincide con ViaCEP" in verificar(respuesta, escenario)
    falso = respuesta.model_copy(update={"uf": "RJ"})
    assert "ubicación no coincide con ViaCEP" in verificar(falso, escenario,
                                                            observaciones=[observacion])


def test_politica_exige_fragmento_y_entailment(tmp_path):
    escenario = crear_escenario(tmp_path)
    doc = Document(page_content="La devolución ficticia se admite dentro de 30 días.")
    indice = SimpleNamespace(docstore=SimpleNamespace(search=lambda _id: doc))
    respuesta = RespuestaCompra(estado="politica", dataset_id=escenario.dataset_id,
        solicitud=Solicitud(), mensaje="La devolución ficticia se admite dentro de 30 días.",
        evidencias=[Evidencia(tipo="politica", fuente_id="politica-1", texto=doc.page_content)])
    assert verificar(respuesta, escenario, indice=indice) == []
    assert verificar(respuesta, escenario) == ["política sin índice o afirmación"]
    alterada = respuesta.model_copy(update={"evidencias": [Evidencia(
        tipo="politica", fuente_id="politica-1", texto="texto inventado")]})
    assert verificar(alterada, escenario, indice=indice)

    class Etiqueta:
        def __init__(self, etiqueta):
            self.etiqueta = etiqueta
        def clasificar(self, premisa, hipotesis):
            return self.etiqueta

    assert verificar_nli(respuesta, Etiqueta("entailment"))
    assert not verificar_nli(respuesta, Etiqueta("neutral"))
    assert not verificar_nli(respuesta, Etiqueta("contradiction"))


def test_flujo_publica_cep_solo_tras_observacion(tmp_path, monkeypatch):
    import pedro.agent as modulo
    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    respuesta = RespuestaCompra(estado="cep", dataset_id=escenario.dataset_id,
        solicitud=Solicitud(cep="01001000"), cidade="São Paulo", uf="SP", modo_cep="real",
        evidencias=[Evidencia(tipo="viacep", fuente_id="ViaCEP:01001000", texto="São Paulo/SP")])
    class Executor:
        def invoke(self, entrada, config):
            return {"output": respuesta.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_cep"),
                 '{"estado":"ok","cep":"01001000","cidade":"São Paulo","uf":"SP","modo":"real"}')]
            }
    monkeypatch.setattr(modulo, "crear_agente", lambda *args, **kwargs: Executor())
    flujo = crear_flujo(escenario, memoria, llm=object())
    salida = flujo.invoke({"input": "Consulta CEP 01001000"}, config={"configurable": {
        "user_id": "ana", "session_id": sesion}})
    assert "São Paulo/SP" in salida.content
    assert len(Historial(memoria, "ana", sesion).todos()) == 2
