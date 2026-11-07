from compraslab.nli import verificar_nli
from compraslab.schemas import Evidencia, Oferta, Alternativa, RespuestaCompra, SolicitudCompra


class ClasificadorGuionado:
    def __init__(self, etiqueta):
        self.etiqueta = etiqueta
    def clasificar(self, premisa, hipotesis):
        assert "Demo A" in premisa and "Demo A" in hipotesis
        return self.etiqueta


def test_nli_triclase_no_aprueba_neutral_o_contradiccion():
    oferta = Oferta(dataset_id="d", id="o", producto_id="PROD-1", proveedor_id="A",
        proveedor_nombre="Demo A", precio_unitario_centavos=100, flete_centavos=0,
        stock=4, plazo_dias=2)
    respuesta = RespuestaCompra(estado="recomendacion", mensaje="demo", dataset_id="d",
        solicitud=SolicitudCompra(producto_id="PROD-1", cantidad=1,
                                  presupuesto_centavos=100, plazo_max_dias=2),
        producto_id="PROD-1", proveedor_id="A", total_centavos=100,
        alternativas=[Alternativa(oferta=oferta, total_centavos=100, cumple=True)],
        evidencias=[Evidencia(tipo="catalogo", fuente_id="o", dataset_id="d",
                              texto="Demo A stock 4, plazo 2")])
    assert verificar_nli(respuesta, ClasificadorGuionado("entailment"))
    assert not verificar_nli(respuesta, ClasificadorGuionado("neutral"))
    assert not verificar_nli(respuesta, ClasificadorGuionado("contradiction"))
