"""Contratos públicos. Ausências são sempre null, nunca zero implícito."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Solicitacao(BaseModel):
    produto_id: str | None = None
    produto: str | None = None
    quantidade: int | None = Field(default=None, gt=0)
    orcamento_centavos: int | None = Field(default=None, ge=0)
    prazo_max_dias: int | None = Field(default=None, ge=0)
    cep: str | None = None
    # Preferência salva do usuário; quem a define é o sistema, não a mensagem nem o modelo.
    origem_preferida: Literal["nacional", "internacional"] | None = None

    @model_validator(mode="after")
    def validar_produto(self):
        if self.produto is not None and not self.produto.strip():
            raise ValueError("produto vazio")
        return self

    def faltantes(self) -> list[str]:
        faltam = []
        if not (self.produto_id or self.produto):
            faltam.append("produto")
        if self.quantidade is None:
            faltam.append("quantidade")
        return faltam


class Extracao(BaseModel):
    intencao: Literal["consultar", "comparar", "politica", "cep", "preferencia", "outro"]
    solicitacao: Solicitacao
    faltantes: list[str]


class ExtracaoRaciocinada(BaseModel):
    """Extração com chain-of-thought visível: o raciocínio é escrito antes dos dados."""
    raciocinio: list[str] = Field(description="Passos breves: o que o texto diz sobre produto, "
                                              "quantidade, orçamento e prazo, e o que não diz")
    intencao: Literal["consultar", "comparar", "politica", "cep", "preferencia", "outro"]
    solicitacao: Solicitacao
    faltantes: list[str]


class Oferta(BaseModel):
    dataset_id: str
    id: str
    produto_id: str
    fornecedor_id: str
    fornecedor_nome: str
    preco_unitario_centavos: int = Field(ge=0)
    frete_centavos: int = Field(ge=0)
    estoque: int = Field(ge=0)
    prazo_dias: int = Field(ge=0)
    pedido_minimo: int = Field(default=1, ge=1)
    nacional: bool = True
    # Histórico do preço unitário: observações mensais anteriores à vigente.
    meses_historico: int = Field(default=0, ge=0)
    preco_anterior_centavos: int | None = Field(default=None, ge=0)
    preco_medio_centavos: int | None = Field(default=None, ge=0)
    preco_minimo_centavos: int | None = Field(default=None, ge=0)
    preco_maximo_centavos: int | None = Field(default=None, ge=0)


class Alternativa(BaseModel):
    oferta: Oferta
    total_centavos: int
    atende: bool
    motivos: list[Literal["estoque", "pedido_minimo", "prazo", "orcamento"]] = Field(default_factory=list)


class Evidencia(BaseModel):
    tipo: Literal["catalogo", "politica", "viacep", "memoria"]
    fonte_id: str
    texto: str
    dataset_id: str | None = None


class RespostaCompra(BaseModel):
    estado: Literal["esclarecimento", "recomendacao", "sem_oferta", "sem_evidencia", "cep", "politica",
                    "preferencia", "catalogo"]
    dataset_id: str
    solicitacao: Solicitacao
    produto_id: str | None = None
    fornecedor_id: str | None = None
    total_centavos: int | None = None
    alternativas: list[Alternativa] = Field(default_factory=list)
    evidencias: list[Evidencia] = Field(default_factory=list)
    mensagem: str = ""
    cidade: str | None = None
    uf: str | None = None
    modo_cep: Literal["real", "simulado"] | None = None
