"""Text-to-query: o modelo compila um plano, nunca SQL livre."""
import re
from typing import Literal

from pydantic import BaseModel, Field

from .catalog import Cenario, conectar


class PlanoConsulta(BaseModel):
    objetivo: Literal["peca", "ofertas"]
    produto_id: str = Field(pattern=r"^PEC-[0-9]{2}-[0-9]{4}$")
    limite: int = Field(default=20, ge=1, le=50)


SQL = {
    "peca": "SELECT id,sku,name,description FROM parts WHERE id=? LIMIT ?",
    "ofertas": "SELECT o.id,o.part_id,o.supplier_id,s.name AS fornecedor,"
               "o.estimated_brl_cents,o.shipping_brl_cents,o.stock_qty,o.lead_days "
               "FROM offers o JOIN suppliers s ON s.id=o.supplier_id "
               "WHERE o.part_id=? ORDER BY o.supplier_id LIMIT ?",
}


def planejar(pergunta: str) -> PlanoConsulta:
    ids = set(re.findall(r"\bPEC-[0-9]{2}-[0-9]{4}\b", pergunta.upper()))
    if len(ids) != 1:
        raise ValueError("é necessário um único ID de peça")
    objetivo = "ofertas" if re.search(r"oferta|pre[cç]o|estoque|fornecedor|prazo", pergunta, re.I) else "peca"
    return PlanoConsulta(objetivo=objetivo, produto_id=ids.pop())


def executar(cenario: Cenario, pergunta: str, plano: PlanoConsulta) -> dict:
    sql = SQL[plano.objetivo]
    parametros = [plano.produto_id, plano.limite]
    with conectar(cenario) as db:
        linhas = [dict(linha) for linha in db.execute(sql, parametros)]
    return {"pergunta": pergunta, "plano": plano.model_dump(), "sql": sql,
            "parametros": parametros, "linhas": linhas, "dataset_id": cenario.dataset_id}


# --- Text-to-SQL com modelo: o LLM escreve o SELECT e o motor decide se o executa. ---

# Tabelas e colunas que uma consulta gerada pode ler. O que não está aqui não existe.
ESQUEMA_PERMITIDO: dict[str, tuple[str, ...]] = {
    "parts": ("id", "sku", "category_id", "family", "name", "description", "manufacturer",
              "part_kind", "material", "color", "voltage_v", "power_w", "weight_g",
              "warranty_months", "origin_country", "condition"),
    "categories": ("id", "slug", "name"),
    "suppliers": ("id", "name", "country_code", "domestic", "currency"),
    "offers": ("id", "part_id", "supplier_id", "estimated_brl_cents", "shipping_brl_cents",
               "stock_qty", "availability", "lead_days", "min_order_qty"),
    "compatibility": ("part_id", "brand", "model_code", "year_from", "year_to"),
    "price_history": ("offer_id", "observed_on", "estimated_brl_cents"),
}
FUNCOES_PERMITIDAS = {"count", "sum", "avg", "min", "max", "round", "lower", "upper", "length",
                      "substr", "coalesce", "abs", "like", "total"}
MAX_LINHAS = 50
MAX_PASSOS = 2_000_000


class ConsultaSQL(BaseModel):
    """O que o modelo deve devolver: uma única consulta de leitura e a sua explicação."""
    sql: str = Field(description="Um único SELECT de SQLite, sem ponto e vírgula final")
    explicacao: str = Field(description="Uma frase: o que a consulta responde")


class ConsultaRejeitada(ValueError):
    """A consulta gerada não passou na validação ou o motor não a autorizou."""


def descrever_esquema() -> str:
    return "\n".join(f"- {tabela}({', '.join(colunas)})"
                     for tabela, colunas in ESQUEMA_PERMITIDO.items())


def validar_sql(sql: str) -> str:
    """Verificação de forma antes de tocar na base: uma única instrução e que seja SELECT."""
    limpo = sql.strip().rstrip(";").strip()
    if not limpo:
        raise ConsultaRejeitada("consulta vazia")
    if ";" in limpo:
        raise ConsultaRejeitada("só é admitida uma instrução")
    if not re.match(r"(?is)^select\b", limpo):
        raise ConsultaRejeitada("só são admitidas consultas SELECT")
    if re.search(r"--|/\*", limpo):
        raise ConsultaRejeitada("não são admitidos comentários")
    return limpo


def consultar_sql(cenario: Cenario, sql: str) -> dict:
    """Valida e executa um SELECT gerado, com o motor como árbitro.

    Três barreiras: a forma (uma instrução SELECT), o autorizador do SQLite (só as tabelas,
    colunas e funções permitidas; qualquer outra ação é negada) e os limites (base em
    somente leitura, 50 linhas no máximo e teto de passos de execução).
    """
    import sqlite3

    limpo = validar_sql(sql)
    negado: list[str] = []

    def autorizar(acao, arg1, arg2, _base, _origem):
        if acao == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if acao == sqlite3.SQLITE_READ:
            if arg1 in ESQUEMA_PERMITIDO and (not arg2 or arg2 in ESQUEMA_PERMITIDO[arg1]):
                return sqlite3.SQLITE_OK
            negado.append(f"leitura de {arg1}.{arg2 or '*'}")
            return sqlite3.SQLITE_DENY
        if acao == sqlite3.SQLITE_FUNCTION and str(arg2).lower() in FUNCOES_PERMITIDAS:
            return sqlite3.SQLITE_OK
        negado.append(f"ação {acao} sobre {arg1 or arg2}")
        return sqlite3.SQLITE_DENY

    passos = [0]

    def vigiar() -> int:
        passos[0] += 10_000
        return 1 if passos[0] > MAX_PASSOS else 0

    with conectar(cenario) as db:
        db.set_authorizer(autorizar)
        db.set_progress_handler(vigiar, 10_000)
        try:
            cursor = db.execute(limpo)
            linhas = [dict(linha) for linha in cursor.fetchmany(MAX_LINHAS + 1)]
        except sqlite3.Error as exc:
            motivo = "; ".join(negado) or str(exc)
            raise ConsultaRejeitada(f"o motor não autorizou a consulta: {motivo}") from exc
        finally:
            db.set_authorizer(None)
            db.set_progress_handler(None, 0)
    return {"sql": limpo, "linhas": linhas[:MAX_LINHAS], "truncado": len(linhas) > MAX_LINHAS,
            "dataset_id": cenario.dataset_id}


def criar_gerador_sql(modelo):
    """Cadeia que converte uma pergunta em uma `ConsultaSQL`. Não executa nada."""
    from langchain_core.output_parsers import PydanticOutputParser

    from .prompts import MODELO_SQL

    parser = PydanticOutputParser(pydantic_object=ConsultaSQL)
    return (MODELO_SQL.partial(esquema=descrever_esquema(), max_linhas=str(MAX_LINHAS),
                               formato=parser.get_format_instructions()) | modelo | parser)


def responder_sql(cenario: Cenario, pergunta: str, gerador) -> dict:
    """Text-to-SQL completo: gerar, validar, executar e, se falhar, corrigir uma vez."""
    tentativas = []
    erro = ""
    for _ in range(2):
        try:
            consulta: ConsultaSQL = gerador.invoke({"pergunta": pergunta, "erro": erro})
        except Exception as exc:  # saída ilegível do modelo
            tentativas.append({"sql": None, "erro": type(exc).__name__})
            erro = "A resposta anterior não era o JSON pedido."
            continue
        try:
            resultado = consultar_sql(cenario, consulta.sql)
        except ConsultaRejeitada as exc:
            tentativas.append({"sql": consulta.sql, "erro": str(exc)})
            erro = f"A consulta anterior foi rejeitada: {exc}. Consulta rejeitada: {consulta.sql}"
            continue
        tentativas.append({"sql": resultado["sql"], "erro": None})
        # Uma consulta válida pode estar mal formulada: zero linhas é sinalizado, não dado como bom.
        estado = "ok" if resultado["linhas"] else "sem_linhas"
        return {"pergunta": pergunta, "estado": estado, "explicacao": consulta.explicacao,
                "tentativas": tentativas, **resultado}
    return {"pergunta": pergunta, "estado": "rejeitada", "tentativas": tentativas, "linhas": [],
            "dataset_id": cenario.dataset_id}
