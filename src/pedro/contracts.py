"""Contratos públicos. Ausencias siempre son null, nunca cero implícito."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Solicitud(BaseModel):
    producto_id: str | None = None
    producto: str | None = None
    cantidad: int | None = Field(default=None, gt=0)
    presupuesto_centavos: int | None = Field(default=None, ge=0)
    plazo_max_dias: int | None = Field(default=None, ge=0)
    cep: str | None = None

    @model_validator(mode="after")
    def validar_producto(self):
        if self.producto is not None and not self.producto.strip():
            raise ValueError("producto vacío")
        return self

    def faltantes(self) -> list[str]:
        faltan = []
        if not (self.producto_id or self.producto):
            faltan.append("producto")
        if self.cantidad is None:
            faltan.append("cantidad")
        return faltan


class Extraccion(BaseModel):
    intencion: Literal["consultar", "comparar", "politica", "cep", "preferencia", "otro"]
    solicitud: Solicitud
    faltantes: list[str]


class ExtraccionRazonada(BaseModel):
    """Extracción con chain-of-thought visible: el razonamiento se escribe antes que los datos."""
    razonamiento: list[str] = Field(description="Pasos breves: qué dice el texto sobre producto, "
                                                "cantidad, presupuesto y plazo, y qué no dice")
    intencion: Literal["consultar", "comparar", "politica", "cep", "preferencia", "otro"]
    solicitud: Solicitud
    faltantes: list[str]


class Oferta(BaseModel):
    dataset_id: str
    id: str
    producto_id: str
    proveedor_id: str
    proveedor_nombre: str
    precio_unitario_centavos: int = Field(ge=0)
    flete_centavos: int = Field(ge=0)
    stock: int = Field(ge=0)
    plazo_dias: int = Field(ge=0)


class Alternativa(BaseModel):
    oferta: Oferta
    total_centavos: int
    cumple: bool
    motivos: list[Literal["stock", "plazo", "presupuesto"]] = Field(default_factory=list)


class Evidencia(BaseModel):
    tipo: Literal["catalogo", "politica", "viacep", "memoria"]
    fuente_id: str
    texto: str
    dataset_id: str | None = None


class RespuestaCompra(BaseModel):
    estado: Literal["aclaracion", "recomendacion", "sin_oferta", "sin_evidencia", "cep", "politica",
                    "preferencia"]
    dataset_id: str
    solicitud: Solicitud
    producto_id: str | None = None
    proveedor_id: str | None = None
    total_centavos: int | None = None
    alternativas: list[Alternativa] = Field(default_factory=list)
    evidencias: list[Evidencia] = Field(default_factory=list)
    mensaje: str = ""
    cidade: str | None = None
    uf: str | None = None
    modo_cep: Literal["real", "simulado"] | None = None
