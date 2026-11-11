"""Converte o relatório Markdown em um PDF legível e reproduzível.

Admite um subconjunto de Markdown: títulos (#, ##, ###), parágrafos, listas com hífen,
tabelas com barras e **negrito**. Não executa nada: só diagrama docs/relatorio.md.
"""
import re
import sys
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
# Sem argumentos gera o relatório; com `<origem.md> <destino.pdf> [título]` gera outro documento.
ORIGEM = Path(sys.argv[1]).resolve() if len(sys.argv) > 2 else ROOT / "docs/relatorio.md"
DESTINO = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else ROOT / "docs/relatorio.pdf"
TITULO = sys.argv[3] if len(sys.argv) > 3 else "Relatório técnico — Pedro"
FONTE = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
NEGRITO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
if FONTE.is_file() and NEGRITO.is_file():
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONTE)))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(NEGRITO)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold")
    font, font_negrito = "DejaVu", "DejaVu-Bold"
else:
    font, font_negrito = "Helvetica", "Helvetica-Bold"

AZUL = colors.HexColor("#283963")
LARGURA = A4[0] - 96
estilos = {
    "titulo": ParagraphStyle("titulo", fontName=font_negrito, fontSize=17, leading=22,
                             textColor=AZUL, spaceAfter=10),
    "secao": ParagraphStyle("secao", fontName=font_negrito, fontSize=12.5, leading=17,
                              textColor=AZUL, spaceBefore=14, spaceAfter=6),
    "subsecao": ParagraphStyle("subsecao", fontName=font_negrito, fontSize=10, leading=14,
                                 textColor=AZUL, spaceBefore=8, spaceAfter=4),
    "texto": ParagraphStyle("texto", fontName=font, fontSize=8.8, leading=13.5,
                            alignment=TA_LEFT, spaceAfter=6),
    "lista": ParagraphStyle("lista", fontName=font, fontSize=8.8, leading=13.5,
                            leftIndent=12, bulletIndent=2, spaceAfter=2),
    "celula": ParagraphStyle("celula", fontName=font, fontSize=7.6, leading=10.5),
    "cabecalho": ParagraphStyle("cabecalho", fontName=font_negrito, fontSize=7.6, leading=10.5,
                               textColor=colors.white),
}


def marcar(texto: str) -> str:
    """Escapa o texto e converte **negrito** e `código` para a marcação do ReportLab."""
    texto = escape(texto)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    return re.sub(r"`(.+?)`", r"\1", texto)


def tabela(linhas_texto: list[str]) -> Table:
    linhas = [[celula.strip() for celula in linha.strip().strip("|").split("|")] for linha in linhas_texto]
    linhas = [linha for linha in linhas if not all(re.fullmatch(r":?-+:?", celula) for celula in linha)]
    colunas = len(linhas[0])
    # Reparte a largura conforme o texto mais longo de cada coluna, com um mínimo razoável.
    pesos = [max(8, min(60, max(len(linha[i]) for linha in linhas if i < len(linha))))
             for i in range(colunas)]
    larguras = [LARGURA * peso / sum(pesos) for peso in pesos]
    dados = [[Paragraph(marcar(celula), estilos["cabecalho" if numero == 0 else "celula"])
              for celula in linha] for numero, linha in enumerate(linhas)]
    objeto = Table(dados, colWidths=larguras, repeatRows=1)
    objeto.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8bfd0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5fa")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return objeto


elementos = []
for bloco in ORIGEM.read_text(encoding="utf-8").split("\n\n"):
    linhas = [linha for linha in bloco.strip().splitlines() if linha.strip()]
    if not linhas:
        continue
    primeira = linhas[0]
    if primeira.startswith("# "):
        elementos.append(Paragraph(marcar(primeira[2:]), estilos["titulo"]))
    elif primeira.startswith("## "):
        elementos.append(Paragraph(marcar(primeira[3:]), estilos["secao"]))
    elif primeira.startswith("### "):
        elementos.append(Paragraph(marcar(primeira[4:]), estilos["subsecao"]))
    elif all(linha.lstrip().startswith("|") for linha in linhas):
        elementos.append(tabela(linhas))
        elementos.append(Spacer(1, 7))
    elif all(linha.lstrip().startswith("- ") for linha in linhas):
        for linha in linhas:
            elementos.append(Paragraph(marcar(linha.lstrip()[2:]), estilos["lista"], bulletText="•"))
        elementos.append(Spacer(1, 4))
    else:
        elementos.append(Paragraph(marcar(" ".join(linhas)), estilos["texto"]))

SimpleDocTemplate(str(DESTINO), pagesize=A4, leftMargin=48, rightMargin=48, topMargin=48,
                  bottomMargin=48, title=TITULO,
                  author="Projeto Pedro (Infnet)").build(elementos)
print(DESTINO)
