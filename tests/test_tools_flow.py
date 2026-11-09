import json

from pedro.agent import Traza, crear_flujo, herramientas
from pedro.catalog import crear_escenario
from pedro.memory import Historial, nueva_sesion
from pedro.query import ejecutar, planear


def test_sql_plan_y_herramientas(tmp_path):
    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    nueva_sesion(memoria, "ana", escenario.dataset_id)
    resultado = ejecutar(escenario, "ofertas PEC-01-0001", planear("ofertas PEC-01-0001"))
    assert len(resultado["filas"]) == 3
    assert resultado["parametros"] == ["PEC-01-0001", 20]
    assert "?" in resultado["sql"]
    assert len(herramientas(escenario, memoria, "ana", "hola")) == 6


def test_traza_oculta_claves_y_registra_fuentes():
    traza = Traza()
    traza.on_tool_start({"name": "consultar_catalogo"}, "sk-abcdefghijklmnop")
    traza.on_tool_end('{"evidencias":[{"fuente_id":"oferta-1"}]}')
    assert "sk-" not in traza.eventos[0]["entrada"]
    assert traza.eventos[0]["ruta"] == "consultar_catalogo"
    assert traza.eventos[1]["fuentes"] == ["oferta-1"]


def test_flujo_local_persiste_solo_publico(tmp_path):
    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    flujo = crear_flujo(escenario, memoria)
    salida = flujo.invoke({"input": "lista piezas"}, config={"configurable": {
        "user_id": "ana", "session_id": sesion}})
    assert "PEC-01-0001" in salida.content
    mensajes = Historial(memoria, "ana", sesion).todos()
    assert [m.type for m in mensajes] == ["human", "ai"]
    assert len(mensajes[1].content.splitlines()) == 21


def test_correccion_interna_y_publicacion_final(tmp_path, monkeypatch):
    import pedro.agent as modulo
    from pedro.contracts import Solicitud
    from pedro.verification import respuesta_local

    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    propuesta = respuesta_local(escenario, Solicitud(producto_id="PEC-01-0001", cantidad=1,
        presupuesto_centavos=10_000_000, plazo_max_dias=60))
    llamadas = []

    class Executor:
        def invoke(self, entrada, config):
            llamadas.append(entrada)
            return {"output": "json inválido" if len(llamadas) == 1 else propuesta.model_dump_json()}

    class NLI:
        def clasificar(self, premisa, hipotesis):
            return "entailment"

    class Vectores:
        modelo, version = "test", "1"
        def embed(self, texto):
            return [1.0]

    monkeypatch.setattr(modulo, "crear_agente", lambda *args, **kwargs: Executor())
    monkeypatch.setattr(modulo, "FastEmbedder", Vectores)
    flujo = crear_flujo(escenario, memoria, llm=object(), clasificador=NLI())
    salida = flujo.invoke({"input": "recomienda 1 unidad de PEC-01-0001; presupuesto R$ 100000 y plazo 60 días"}, config={"configurable": {
        "user_id": "ana", "session_id": sesion}})
    assert len(llamadas) == 2
    assert propuesta.proveedor_id in salida.content or propuesta.alternativas[0].oferta.proveedor_nombre in salida.content
    assert [m.type for m in Historial(memoria, "ana", sesion).todos()] == ["human", "ai"]


def test_modelo_no_publica_cantidad_antigua(tmp_path, monkeypatch):
    import pedro.agent as modulo
    from pedro.contracts import Solicitud
    from pedro.verification import respuesta_local

    escenario = crear_escenario(tmp_path / "catalogos")
    memoria = tmp_path / "memoria.sqlite3"
    sesion = nueva_sesion(memoria, "ana", escenario.dataset_id)
    propuesta_antigua = respuesta_local(escenario, Solicitud(
        producto_id="PEC-01-0001", cantidad=2))
    llamadas = []

    class Executor:
        def invoke(self, entrada, config):
            llamadas.append(entrada)
            return {"output": propuesta_antigua.model_dump_json()}

    monkeypatch.setattr(modulo, "crear_agente", lambda *args, **kwargs: Executor())
    flujo = crear_flujo(escenario, memoria, llm=object())
    salida = flujo.invoke({"input": "Compara 3 unidades de PEC-01-0001"},
                         config={"configurable": {"user_id": "ana", "session_id": sesion}})
    assert len(llamadas) == 2
    assert "No puedo confirmar" in salida.content
