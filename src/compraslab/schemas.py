"""Contratos de negocio. None significa dato faltante, nunca cero."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SolicitudCompra(BaseModel):
    producto: str | None = None
    producto_id: str | None = None
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
        return [x for x in ("producto", "cantidad", "presupuesto_centavos", "plazo_max_dias")
                if (not (self.producto or self.producto_id) if x == "producto" else getattr(self, x) is None)]


class Producto(BaseModel):
    dataset_id: str
    id: str
    nombre: str
    modelo: str
    unidad: str = "unidade"


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


class Evidencia(BaseModel):
    tipo: Literal["catalogo", "politica", "viacep", "memoria"]
    fuente_id: str
    dataset_id: str | None = None
    texto: str


class ResultadoHerramienta(BaseModel):
    nombre: str
    estado: Literal["ok", "no_encontrado", "invalido", "indisponible"]
    datos: dict | list | None = None
    evidencias: list[Evidencia] = Field(default_factory=list)
    error: str | None = None


class Alternativa(BaseModel):
    oferta: Oferta
    total_centavos: int
    cumple: bool
    motivos: list[Literal["stock", "plazo", "presupuesto"]] = Field(default_factory=list)


class RespuestaCompra(BaseModel):
    estado: Literal["aclaracion", "recomendacion", "sin_oferta", "sin_evidencia"]
    mensaje: str
    dataset_id: str
    solicitud: SolicitudCompra
    producto_id: str | None = None
    proveedor_id: str | None = None
    total_centavos: int | None = None
    alternativas: list[Alternativa] = Field(default_factory=list)
    evidencias: list[Evidencia] = Field(default_factory=list)


class ResultadoVerificacion(BaseModel):
    aprobado: bool
    errores: list[str] = Field(default_factory=list)
    nli: Literal["entailment", "contradiction", "neutral", "no_ejecutado"] = "no_ejecutado"
    model_config = ConfigDict(extra="forbid")
