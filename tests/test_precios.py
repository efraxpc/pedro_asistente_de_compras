import json

import pytest
from langchain_core.runnables import RunnableLambda

from pedro.catalog import crear_escenario
from pedro.contracts import Oferta, Solicitud
from pedro.precios import (aconsejar, aviso_de_precio, crear_consejero, hechos_de_precio,
                           senal_precio, verificar_consejo)
from pedro.verification import respuesta_local


def _oferta(actual: int, media: int, **extra) -> Oferta:
    return Oferta(dataset_id="d", id="o", producto_id="PEC-01-0001", proveedor_id="BR-01",
                  proveedor_nombre="Prueba", precio_unitario_centavos=actual, flete_centavos=0,
                  stock=9, plazo_dias=1, meses_historial=5, precio_medio_centavos=media,
                  precio_anterior_centavos=media, precio_minimo_centavos=min(actual, media) - 1,
                  precio_maximo_centavos=max(actual, media) + 1, **extra)


@pytest.mark.parametrize("actual, nivel", [
    (125, "muy por encima"), (120, "muy por encima"), (119, "por encima"), (110, "por encima"),
    (109, "en línea"), (100, "en línea"), (91, "en línea"), (90, "por debajo"),
    (81, "por debajo"), (80, "muy por debajo"),
])
def test_la_senal_clasifica_el_precio_con_umbrales_fijos(actual, nivel):
    senal = senal_precio(_oferta(actual, 100))
    assert senal.nivel == nivel and senal.frente_a_media == actual - 100


def test_sin_historial_no_hay_senal():
    oferta = _oferta(100, 100).model_copy(update={"precio_medio_centavos": None})
    assert senal_precio(oferta) is None


@pytest.fixture
def cara(tmp_path):
    """PEC-02-0189, 5 unidades: gana CentroPeças con el precio 11 % por encima de su media."""
    escenario = crear_escenario(tmp_path / "catalogos")
    return respuesta_local(escenario, Solicitud(producto_id="PEC-02-0189", cantidad=5))


def test_el_aviso_senala_un_precio_alto_y_una_alternativa_casi_igual(cara, tmp_path):
    aviso = aviso_de_precio(cara)
    assert aviso == ("El precio de CentroPeças está 11 % por encima de su media de 5 meses. "
                     "Atlantic Repair Parts cuesta R$ 12,89 más (1 %) y su precio está 10 % por "
                     "debajo de su media.")
    assert cara.proveedor_id == "BR-06"  # el aviso no cambia el ganador
    hechos = hechos_de_precio(cara)
    assert hechos[0].startswith("La oferta recomendada es la de CentroPeças")
    assert any("Atlantic Repair Parts también cumple" in h for h in hechos)
    # Si el precio del ganador está en línea con su media, no se avisa de nada.
    normal = respuesta_local(crear_escenario(tmp_path / "otro"), Solicitud(producto_id="PEC-01-0001", cantidad=5))
    assert aviso_de_precio(normal) is None
    assert aconsejar(normal, None, None) == {"texto": None, "fuente": "nada que avisar"}


def _consejero(texto: str):
    return crear_consejero(RunnableLambda(lambda _: json.dumps({"consejo": texto})))


class NLI:
    def __init__(self, etiqueta):
        self.etiqueta, self.vistos = etiqueta, []

    def clasificar(self, premisa, hipotesis):
        self.vistos.append((premisa, hipotesis))
        return self.etiqueta


BUENO = ("CentroPeças está 11 % por encima de su media de 5 meses; Atlantic Repair Parts cuesta "
         "solo 1 % más y está 10 % por debajo de su media.")


def test_un_consejo_respaldado_sustituye_al_aviso_fijo(cara):
    nli = NLI("entailment")
    resultado = aconsejar(cara, _consejero(BUENO), nli)
    assert resultado["fuente"] == "consejo verificado" and resultado["texto"] == BUENO
    premisa, hipotesis = nli.vistos[0]
    assert hipotesis == BUENO and "11 % por encima" in premisa


@pytest.mark.parametrize("consejo, etiqueta, motivo", [
    ("CentroPeças está 30 % por encima de su media; mejor Atlantic Repair Parts.", "entailment", "cifras"),
    ("Hay una opción mejor que cuesta casi lo mismo y conviene mirarla.", "entailment", "ningún proveedor"),
    ("CentroPeças está 11 % por encima de su media y su precio va a bajar pronto.", "entailment", "predice"),
    (BUENO, "neutral", "NLI: neutral"),
    (BUENO, "contradiction", "NLI: contradiction"),
])
def test_un_consejo_sin_respaldo_se_descarta_y_queda_el_aviso_fijo(cara, consejo, etiqueta, motivo):
    resultado = aconsejar(cara, _consejero(consejo), NLI(etiqueta))
    assert resultado["fuente"] == "aviso fijo" and resultado["texto"] == aviso_de_precio(cara)
    assert resultado["consejo_rechazado"] == consejo
    assert any(motivo in error for error in resultado["errores"])


def test_si_el_modelo_falla_o_no_hay_nli_queda_el_aviso_fijo(cara):
    roto = crear_consejero(RunnableLambda(lambda _: "no es JSON"))
    assert aconsejar(cara, roto, NLI("entailment"))["fuente"] == "aviso fijo"
    assert aconsejar(cara, _consejero(BUENO), None)["errores"] == ["sin clasificador NLI"]
    assert aconsejar(cara, None, None)["fuente"] == "aviso fijo"
    assert verificar_consejo(BUENO, hechos_de_precio(cara), ["CentroPeças"], NLI("entailment")) == []
