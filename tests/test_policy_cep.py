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


def test_cep_se_ancla_a_la_observacion_y_sin_ella_se_rechaza(tmp_path):
    from pedro.verification import anclar_cep

    escenario = crear_escenario(tmp_path / "catalogos")
    observacion = ("consultar_cep", {"estado": "ok", "cep": "01001000", "cidade": "São Paulo",
                                     "uf": "SP", "modo": "real"})
    # El modelo se equivoca en lo mecánico: otro dataset, sin evidencia y con la ciudad mal escrita.
    respuesta = RespuestaCompra(estado="cep", dataset_id="otro", solicitud=Solicitud(cep="01001000"),
                                cidade="Sao Paulo", uf="SP")
    assert verificar(respuesta, escenario, observaciones=[observacion]) == ["dataset ajeno"]
    assert anclar_cep(respuesta, [observacion], escenario.dataset_id)["estado"] == "anclada"
    assert verificar(respuesta, escenario, observaciones=[observacion]) == []
    assert (respuesta.cidade, respuesta.modo_cep) == ("São Paulo", "real")
    assert respuesta.evidencias[0].fuente_id == "ViaCEP:01001000"

    inventada = RespuestaCompra(estado="cep", dataset_id="otro", solicitud=Solicitud(cep="99999999"),
                                cidade="Ciudad Inventada", uf="XX", modo_cep="real")
    sin_dato = ("consultar_cep", {"estado": "no_encontrado", "cep": "99999999"})
    assert anclar_cep(inventada, [sin_dato], escenario.dataset_id)["estado"] == "sin_observacion_valida"
    assert verificar(inventada, escenario, observaciones=[sin_dato]) == ["dataset ajeno"]
    otro_cep = RespuestaCompra(estado="cep", dataset_id=escenario.dataset_id,
                               solicitud=Solicitud(cep="20040020"), cidade="Rio", uf="RJ", modo_cep="real")
    assert anclar_cep(otro_cep, [observacion], escenario.dataset_id)["estado"] == "sin_observacion_valida"
    assert verificar(otro_cep, escenario, observaciones=[observacion]) != []


def test_flujo_explica_un_cep_inexistente_sin_inventar_ciudad(tmp_path, monkeypatch):
    import pedro.agent as modulo
    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    inventada = RespuestaCompra(estado="cep", dataset_id=escenario.dataset_id,
                                solicitud=Solicitud(cep="99999999"), cidade="Ciudad Inventada",
                                uf="XX", modo_cep="real")

    class Executor:
        def invoke(self, entrada, config):
            return {"output": inventada.model_dump_json(), "intermediate_steps": [
                (SimpleNamespace(tool="consultar_cep"), '{"estado":"no_encontrado","cep":"99999999"}')]}

    monkeypatch.setattr(modulo, "crear_agente", lambda *args, **kwargs: Executor())
    flujo = crear_flujo(escenario, memoria, llm=object())
    salida = flujo.invoke({"input": "Consulta CEP 99999999"}, config={"configurable": {
        "user_id": "ana", "session_id": sesion}})
    assert salida.content == "ViaCEP no tiene registrado el CEP 99999999."
    assert "Inventada" not in salida.content
