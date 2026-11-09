import pytest
from langchain_core.messages import AIMessage, HumanMessage

from pedro.catalog import crear_escenario
from pedro.contracts import Solicitud
from pedro.memory import (Historial, actualizar_episodio, guardar_episodio,
                          guardar_preferencia, nueva_sesion, preferencias, recuperar)
from pedro.nli import verificar_nli
from pedro.verification import respuesta_local


class Vectores:
    modelo = "test"
    version = "1"

    def embed(self, texto):
        return [float("azul" in texto), float("rojo" in texto)]


def test_memoria_aislada_y_actualizada(tmp_path):
    ruta = tmp_path / "memoria.sqlite3"
    a = nueva_sesion(ruta, "ana", "dataset-a")
    b = nueva_sesion(ruta, "beto", "dataset-b")
    ha = Historial(ruta, "ana", a)
    ha.add_messages([HumanMessage(content="quiero dos"), AIMessage(content="entendido")])
    assert len(ha.todos()) == 2
    with pytest.raises(ValueError):
        Historial(ruta, "beto", a)
    for i in range(14):
        ha.add_messages([HumanMessage(content=f"turno {i}")])
    assert len(ha.messages) == 12
    assert len(ha.todos()) == 16
    guardar_preferencia(ruta, "ana", "color", "azul", explicita=True)
    assert preferencias(ruta, "beto") == {}
    episodio = guardar_episodio(ruta, "ana", a, "azul", Vectores())
    assert recuperar(ruta, "ana", "azul", Vectores())[0]["id"] == episodio
    assert recuperar(ruta, "beto", "azul", Vectores()) == []
    actualizar_episodio(ruta, "ana", episodio, "rojo", Vectores())
    assert recuperar(ruta, "ana", "rojo", Vectores())[0]["texto"] == "rojo"


@pytest.mark.parametrize("etiqueta,esperado", [("entailment", True),
                                               ("contradiction", False), ("neutral", False)])
def test_nli_triclase(tmp_path, etiqueta, esperado):
    escenario = crear_escenario(tmp_path)
    respuesta = respuesta_local(escenario, Solicitud(producto_id="PEC-01-0001", cantidad=1,
        presupuesto_centavos=10_000_000, plazo_max_dias=60))

    class Clasificador:
        def clasificar(self, premisa, hipotesis):
            assert respuesta.proveedor_id in hipotesis or "stock" in hipotesis
            return etiqueta

    assert verificar_nli(respuesta, Clasificador()) is esperado
