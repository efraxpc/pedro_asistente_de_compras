"""Cenários imutáveis a partir de uma base sintética reproduzível."""
import hashlib
import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .contracts import Oferta

SOURCE = Path(__file__).resolve().parents[2] / "datasets/pecas_eletrodomesticos.sqlite3"


@dataclass(frozen=True)
class Cenario:
    dataset_id: str
    caminho: Path


def conectar(cenario: Cenario) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{cenario.caminho}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def criar_cenario(base: Path, source: Path = SOURCE) -> Cenario:
    if not source.is_file():
        raise FileNotFoundError(source)
    identificador = str(uuid.uuid4())
    pasta = base / identificador
    pasta.mkdir(parents=True, exist_ok=False)
    destino = pasta / "catalogo.sqlite3"
    shutil.copyfile(source, destino)
    impressao = hashlib.sha256(destino.read_bytes()).hexdigest()
    cenario = Cenario(identificador, destino)
    with conectar(cenario) as db:
        contagens = {tabela: db.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]
                     for tabela in ("parts", "offers", "compatibility", "price_history")}
        semente = db.execute("SELECT value FROM metadata WHERE key='seed'").fetchone()[0]
    manifesto = {"dataset_id": identificador, "version": "synthetic-parts-v1",
                 "capturado_em": datetime.now(timezone.utc).isoformat(),
                 "fonte": str(source.resolve()), "semente": int(semente),
                 "sha256": impressao, "contagens": contagens}
    (pasta / "manifest.json").write_text(json.dumps(manifesto, indent=2), encoding="utf-8")
    return cenario


def abrir_cenario(base: Path, dataset_id: str) -> Cenario:
    uuid.UUID(dataset_id)
    pasta = base / dataset_id
    meta = json.loads((pasta / "manifest.json").read_text(encoding="utf-8"))
    caminho = pasta / "catalogo.sqlite3"
    if meta["dataset_id"] != dataset_id or hashlib.sha256(caminho.read_bytes()).hexdigest() != meta["sha256"]:
        raise ValueError("manifesto ou catálogo alterado")
    return Cenario(dataset_id, caminho)


def buscar(cenario: Cenario, texto: str, limite: int = 20) -> list[dict]:
    if not texto.strip():
        return []
    padrao = f"%{texto.strip().lower()}%"
    with conectar(cenario) as db:
        linhas = db.execute("SELECT p.id,p.sku,p.name,c.name AS category FROM parts p "
                            "JOIN categories c ON c.id=p.category_id WHERE lower(p.id)=? "
                            "OR lower(p.sku)=? OR lower(p.name) LIKE ? ORDER BY p.id LIMIT ?",
                            (texto.lower(), texto.lower(), padrao, min(max(limite, 1), 50))).fetchall()
    return [dict(linha) for linha in linhas]


def listar(cenario: Cenario, pagina: int = 1, termo: str = "") -> tuple[int, list[dict]]:
    if pagina < 1:
        raise ValueError("página inválida")
    padrao = f"%{termo.strip().lower()}%"
    filtro = "WHERE lower(p.name) LIKE ? OR lower(p.sku) LIKE ? OR lower(p.id) LIKE ?"
    with conectar(cenario) as db:
        total = db.execute(f"SELECT count(*) FROM parts p {filtro}", (padrao,) * 3).fetchone()[0]
        linhas = db.execute(f"SELECT p.id,p.sku,p.name,c.name AS category FROM parts p "
                            f"JOIN categories c ON c.id=p.category_id {filtro} "
                            "ORDER BY p.id LIMIT 20 OFFSET ?", (*((padrao,) * 3), (pagina - 1) * 20)).fetchall()
    return total, [dict(linha) for linha in linhas]


def ficha(cenario: Cenario, produto_id: str) -> dict | None:
    with conectar(cenario) as db:
        linha = db.execute("SELECT p.*,c.name AS category FROM parts p JOIN categories c "
                           "ON c.id=p.category_id WHERE p.id=?", (produto_id,)).fetchone()
        if linha is None:
            return None
        dado = dict(linha)
        dado["compatibility"] = [dict(c) for c in db.execute(
            "SELECT brand,model_code,year_from,year_to FROM compatibility WHERE part_id=?", (produto_id,))]
    return dado


def ofertas(cenario: Cenario, produto_id: str) -> list[Oferta]:
    with conectar(cenario) as db:
        linhas = db.execute("SELECT o.id,o.part_id AS produto_id,o.supplier_id AS fornecedor_id,"
                            "s.name AS fornecedor_nome,o.estimated_brl_cents AS preco_unitario_centavos,"
                            "o.shipping_brl_cents AS frete_centavos,o.stock_qty AS estoque,"
                            "o.lead_days AS prazo_dias,o.min_order_qty AS pedido_minimo,"
                            "s.domestic AS nacional FROM offers o JOIN suppliers s ON s.id=o.supplier_id "
                            "WHERE o.part_id=? ORDER BY o.supplier_id", (produto_id,)).fetchall()
        historicos: dict[str, list[int]] = {}
        marcas = ",".join("?" * len(linhas))
        for oferta_id, preco in db.execute(
                f"SELECT offer_id,estimated_brl_cents FROM price_history WHERE offer_id IN ({marcas}) "
                "ORDER BY offer_id,observed_on", [linha["id"] for linha in linhas]):
            historicos.setdefault(oferta_id, []).append(preco)
    return [Oferta(dataset_id=cenario.dataset_id, **dict(linha), **_resumo_historico(
        historicos.get(linha["id"], []), linha["preco_unitario_centavos"])) for linha in linhas]


def _resumo_historico(precos: list[int], vigente: int) -> dict:
    """Resume o histórico de uma oferta em centavos inteiros.

    A última observação é o preço vigente; a média e o preço anterior são calculados
    com as anteriores. A média é arredondada ao centavo mais próximo sem usar decimais.
    """
    anteriores = precos[:-1] if precos and precos[-1] == vigente else precos
    if not anteriores:
        return {}
    return {"meses_historico": len(anteriores), "preco_anterior_centavos": anteriores[-1],
            "preco_medio_centavos": (2 * sum(anteriores) + len(anteriores)) // (2 * len(anteriores)),
            "preco_minimo_centavos": min(*anteriores, vigente),
            "preco_maximo_centavos": max(*anteriores, vigente)}
