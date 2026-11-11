"""Completa uma solicitação por turnos sem inventar restrições comerciais."""
import re
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field

from .catalog import Cenario, buscar, ficha
from .contracts import Solicitacao

PALAVRAS_IGNORADAS = {"agora", "busco", "procuro", "comparar", "compara", "compare", "comprar",
                      "quanto", "custa", "dias", "preciso", "oferta", "ofertas", "para",
                      "peca", "peça", "pecas", "peças", "prazo", "preco", "preço",
                      "orcamento", "orçamento", "quero", "recomenda", "recomende",
                      "reposicao", "reposição", "unidades"}

_UNIDADES = r"(?:unidades?|pe[cç]as?)"


class EstadoCompra(BaseModel):
    solicitacao: Solicitacao = Field(default_factory=Solicitacao)
    esperando: Literal["produto", "quantidade"] | None = None


def _centavos(valor: str) -> int | None:
    numero = valor.strip()
    if "," in numero:
        numero = numero.replace(".", "").replace(",", ".")
    elif "." in numero and len(numero.rsplit(".", 1)[1]) == 3:
        numero = numero.replace(".", "")
    try:
        decimal = Decimal(numero)
    except InvalidOperation:
        return None
    if not decimal.is_finite() or decimal < 0 or int(decimal.as_tuple().exponent) < -2:
        return None
    return int(decimal * 100)


def _quantidade(texto: str, esperando: str | None) -> int | None:
    numero = r"(\d+)"
    padroes = (
        rf"\b{numero}\s*{_UNIDADES}\b",
        rf"\bquantidade(?:\s+(?:de|para))?\s*[:=]?\s*{numero}\b",
        rf"\b(?:agora|quero|preciso(?:\s+de)?|compara|compare|comparar|s[aã]o|seriam?)\s+{numero}\b",
        # Mudanças ditas de passagem: «que sejam 3», «melhor 4», «muda para 5».
        rf"\b(?:sejam|melhor|mud(?:a|e|ar)\s+para|sob(?:e|a|ir)\s+para|aument(?:a|e|ar)\s+para|"
        rf"baix(?:a|e|ar)\s+para|diminu(?:i|a|ir)\s+para)\s+{numero}\b"
        r"(?!\s*(?:dias?|semanas?|reais|mil)\b|[.,]\d)",
    )
    for padrao in padroes:
        if coincidencia := re.search(padrao, texto, re.I):
            return int(coincidencia.group(1))
    if esperando == "quantidade" and (coincidencia := re.fullmatch(
            rf"\s*(\d+)\s*{_UNIDADES}?"
            r"\s*(?:,?\s*por favor)?[.!]?\s*", texto, re.I)):
        return int(coincidencia.group(1))
    if re.search(r"\bmeia\s+d[uú]zia\b", texto, re.I):
        return 6
    if re.search(r"\buma\s+d[uú]zia\b", texto, re.I):
        return 12
    if re.search(r"\bum\s+par\b", texto, re.I):
        return 2
    palavras = {"uma": 1, "um": 1, "duas": 2, "dois": 2, "tres": 3, "três": 3, "quatro": 4,
                "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10}
    nomes = "|".join(palavras)
    if coincidencia := re.search(rf"\b({nomes})\s+{_UNIDADES}\b", texto, re.I):
        return palavras[coincidencia.group(1).lower()]
    if coincidencia := re.search(rf"\b(?:agora|sejam|melhor|quantidade\s+(?:de|para)?)\s*({nomes})\b"
                                 r"(?!\s*(?:dias?|semanas?)\b)", texto, re.I):
        return palavras[coincidencia.group(1).lower()]
    if esperando == "quantidade" and texto.lower().strip(" .!") in palavras:
        return palavras[texto.lower().strip(" .!")]
    if re.search(r"\bpre[cç]o\s+unit[aá]rio\b|\bpre[cç]o\s+d[eoa]\b", texto, re.I):
        return 1
    return None


def _candidatos(cenario: Cenario, texto: str) -> list[dict]:
    tokens = [x for x in re.findall(r"[\w-]{4,}", texto.lower())
              if x not in PALAVRAS_IGNORADAS and not x.isdigit()]
    resultados = [buscar(cenario, token, 4) for token in tokens]
    resultados = [x for x in resultados if x]
    return min(resultados, key=len) if resultados else []


def interpretar_compra(cenario: Cenario, previo: EstadoCompra | None,
                       mensagem: str) -> tuple[EstadoCompra, str | None] | None:
    """Devolve um rascunho e, se faltar uma decisão, uma pergunta concreta."""
    texto = mensagem.strip()
    # Perguntas que não são uma compra: CEP, políticas e preferências vão para o agente.
    if re.search(r"\b(cep|pol[ií]ticas?|devolu[cç][aã]o|devolver|garantia|reembolso|compatibilidade|"
                 r"instalar|instala[cç][aã]o|prefer[eê]ncia|prefiro|lembra|lembre|guarda|guarde|"
                 r"salva|salve)\b",
                 texto, re.I):
        return None
    ids = re.findall(r"\bPEC-[0-9]{2}-[0-9]{4}\b", texto.upper())
    intencao = bool(re.search(r"\b(quero|preciso|compara|compare|comparar|recomenda|recomende|"
                              r"cota|cote|cotar|comprar|pre[cç]o|ofertas?)\b", texto, re.I))
    seguimento = previo is not None and bool(re.search(
        r"\b(agora|muda|mude|mudar|mesm[oa]|mant[eé]m|mantenha|quantidade|prazo|or[cç]amento|"
        rf"sejam|melhor|volta|volte|de\s+novo|outra\s+vez)\b|\b\d+\s*{_UNIDADES}\b|R\$",
        texto, re.I))
    if previo is not None and previo.esperando is not None:
        seguimento = True
    if not intencao and not seguimento and not ids:
        return None

    solicitacao = previo.solicitacao.model_copy(deep=True) if previo else Solicitacao()
    esperando = previo.esperando if previo else None
    if len(set(ids)) > 1:
        return EstadoCompra(solicitacao=solicitacao, esperando="produto"), (
            "Qual desses IDs você quer comparar? Indique apenas um.")
    if ids:
        produto_id = ids[0]
        if ficha(cenario, produto_id) is None:
            return EstadoCompra(solicitacao=solicitacao, esperando="produto"), (
                f"Não encontrei {produto_id} neste cenário. Indique outro ID ou SKU.")
        if solicitacao.produto_id != produto_id and not re.search(
                r"\b(mesm[oa]|mant[eé]m|mantenha)\b", texto, re.I):
            solicitacao = Solicitacao()
        solicitacao.produto_id = produto_id
        solicitacao.produto = None
    elif re.search(r"\b(outra|outro)\s+(?:pe[cç]a|produto)\b", texto, re.I):
        solicitacao = Solicitacao()
    elif solicitacao.produto_id is None:
        candidatos = _candidatos(cenario, texto)
        if len(candidatos) == 1:
            solicitacao.produto_id = candidatos[0]["id"]
        elif candidatos:
            opcoes = ", ".join(f"{c['id']} ({c['sku']})" for c in candidatos[:4])
            return EstadoCompra(solicitacao=solicitacao, esperando="produto"), (
                f"Encontrei várias peças. De qual você precisa? {opcoes}.")

    quantidade = _quantidade(texto, esperando)
    if quantidade is not None:
        if quantidade < 1:
            return EstadoCompra(solicitacao=solicitacao, esperando="quantidade"), (
                "De quantas unidades você precisa? Deve ser pelo menos uma.")
        solicitacao.quantidade = quantidade

    if re.search(r"\b(sem|n[aã]o\s+tenho)\s+(?:limite\s+de\s+)?or[cç]amento\b", texto, re.I):
        solicitacao.orcamento_centavos = None
    elif coincidencia := re.search(r"(?:R\$\s*|or[cç]amento(?:\s+m[aá]ximo)?\s*(?:de\s*)?)"
                                   r"(\d[\d.,]*)", texto, re.I):
        if (valor := _centavos(coincidencia.group(1))) is not None:
            solicitacao.orcamento_centavos = valor

    if re.search(r"\b(sem|n[aã]o\s+tenho)\s+(?:limite\s+de\s+)?prazo\b", texto, re.I):
        solicitacao.prazo_max_dias = None
    elif coincidencia := re.search(r"\b(\d+)\s*dias\b|\bprazo(?:\s+m[aá]ximo)?"
                                   r"\s*(?:de\s*)?(\d+)\b", texto, re.I):
        solicitacao.prazo_max_dias = int(coincidencia.group(1) or coincidencia.group(2))

    if solicitacao.produto_id is None:
        return EstadoCompra(solicitacao=solicitacao, esperando="produto"), (
            "De qual peça você precisa? Indique o ID ou SKU; posso buscá-la pelo nome.")
    if solicitacao.quantidade is None:
        return EstadoCompra(solicitacao=solicitacao, esperando="quantidade"), (
            f"De quantas unidades de {solicitacao.produto_id} você precisa? "
            "Posso comparar sem orçamento ou prazo máximo se você não tiver esses limites.")
    return EstadoCompra(solicitacao=solicitacao, esperando=None), None


# --- Interpretação com modelo: as regras resolvem a peça; o modelo, o que se pede. ---

class MudancaSolicitacao(BaseModel):
    """O que uma mensagem muda na solicitação de compra em andamento."""
    e_compra: bool = Field(description="True se a mensagem pede para comparar ou comprar uma peça, "
                                       "ou muda a solicitação em andamento")
    quantidade: int | None = Field(default=None, gt=0)
    orcamento_centavos: int | None = Field(default=None, ge=0)
    prazo_max_dias: int | None = Field(default=None, ge=0)
    remover: list[Literal["orcamento", "prazo"]] = Field(
        default_factory=list, description="Limites que o usuário elimina de forma explícita")


def criar_interprete(modelo):
    """Cadeia few-shot que lê uma mensagem e devolve uma `MudancaSolicitacao`."""
    from langchain_core.output_parsers import PydanticOutputParser

    from .prompts import MODELO_MUDANCA

    parser = PydanticOutputParser(pydantic_object=MudancaSolicitacao)
    return MODELO_MUDANCA.partial(formato=parser.get_format_instructions()) | modelo | parser


def interpretar_turno(cenario: Cenario, previo: EstadoCompra | None, mensagem: str,
                      interprete=None) -> tuple[tuple[EstadoCompra, str | None] | None, dict]:
    """Interpreta um turno combinando regras e modelo. Devolve o resultado e um relatório.

    As regras identificam a peça, que tem formato fixo. Se houver modelo, ele decide se a
    mensagem é uma compra e o que muda em quantidade, orçamento e prazo: entende formas de
    falar que as regras não preveem. Sem modelo, ou se a saída dele não servir, valem as regras.
    """
    regras = interpretar_compra(cenario, previo, mensagem)
    em_andamento = previo is not None and previo.solicitacao.produto_id is not None
    if interprete is None or (regras is None and not em_andamento):
        return regras, {"fonte": "regras"}
    contexto = (previo.solicitacao.model_dump_json(exclude_none=True) if em_andamento and previo
                else "nenhuma")
    try:
        mudanca: MudancaSolicitacao = interprete.invoke({"texto": mensagem, "contexto": contexto})
    except Exception as exc:
        return regras, {"fonte": "regras", "modelo": f"sem resposta útil ({type(exc).__name__})"}
    relatorio = {"fonte": "modelo", "modelo": mudanca.model_dump(exclude_none=True),
                 "regras": None if regras is None else regras[0].solicitacao.model_dump(exclude_none=True)}
    if not mudanca.e_compra:
        return None, relatorio
    if regras is not None and regras[0].esperando == "produto":
        return regras, relatorio  # falta decidir a peça: isso quem pergunta são as regras
    if regras is not None:
        estado = regras[0]
        mesma_peca = previo is not None and previo.solicitacao.produto_id == estado.solicitacao.produto_id
        base = previo.solicitacao if mesma_peca and previo else Solicitacao(
            produto_id=estado.solicitacao.produto_id)
    elif previo is not None:
        base = previo.solicitacao  # as regras não viram uma mudança que o modelo entende
    else:
        return regras, relatorio
    solicitacao = base.model_copy(deep=True)
    for campo in ("quantidade", "orcamento_centavos", "prazo_max_dias"):
        if (valor := getattr(mudanca, campo)) is not None:
            setattr(solicitacao, campo, valor)
    if "orcamento" in mudanca.remover:
        solicitacao.orcamento_centavos = None
    if "prazo" in mudanca.remover:
        solicitacao.prazo_max_dias = None
    if solicitacao.quantidade is None:
        return (EstadoCompra(solicitacao=solicitacao, esperando="quantidade"),
                f"De quantas unidades de {solicitacao.produto_id} você precisa? "
                "Posso comparar sem orçamento ou prazo máximo se você não tiver esses limites."), relatorio
    return (EstadoCompra(solicitacao=solicitacao, esperando=None), None), relatorio
