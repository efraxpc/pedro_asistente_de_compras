"""Convierte el informe Markdown a un PDF legible y reproducible.

Admite un subconjunto de Markdown: títulos (#, ##, ###), párrafos, listas con guion,
tablas con barras y **negrita**. No ejecuta nada: solo maqueta docs/informe.md.
"""
import re
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
ORIGEN = ROOT / "docs/informe.md"
DESTINO = ROOT / "docs/informe.pdf"
FUENTE = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
NEGRITA = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
if FUENTE.is_file() and NEGRITA.is_file():
    pdfmetrics.registerFont(TTFont("DejaVu", str(FUENTE)))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(NEGRITA)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold")
    font, font_negrita = "DejaVu", "DejaVu-Bold"
else:
    font, font_negrita = "Helvetica", "Helvetica-Bold"

AZUL = colors.HexColor("#283963")
ANCHO = A4[0] - 96
estilos = {
    "titulo": ParagraphStyle("titulo", fontName=font_negrita, fontSize=17, leading=22,
                             textColor=AZUL, spaceAfter=10),
    "seccion": ParagraphStyle("seccion", fontName=font_negrita, fontSize=12.5, leading=17,
                              textColor=AZUL, spaceBefore=14, spaceAfter=6),
    "subseccion": ParagraphStyle("subseccion", fontName=font_negrita, fontSize=10, leading=14,
                                 textColor=AZUL, spaceBefore=8, spaceAfter=4),
    "texto": ParagraphStyle("texto", fontName=font, fontSize=8.8, leading=13.5,
                            alignment=TA_LEFT, spaceAfter=6),
    "lista": ParagraphStyle("lista", fontName=font, fontSize=8.8, leading=13.5,
                            leftIndent=12, bulletIndent=2, spaceAfter=2),
    "celda": ParagraphStyle("celda", fontName=font, fontSize=7.6, leading=10.5),
    "cabecera": ParagraphStyle("cabecera", fontName=font_negrita, fontSize=7.6, leading=10.5,
                               textColor=colors.white),
}


def marcar(texto: str) -> str:
    """Escapa el texto y convierte **negrita** y `código` al marcado de ReportLab."""
    texto = escape(texto)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    return re.sub(r"`(.+?)`", r"\1", texto)


def tabla(lineas: list[str]) -> Table:
    filas = [[celda.strip() for celda in linea.strip().strip("|").split("|")] for linea in lineas]
    filas = [fila for fila in filas if not all(re.fullmatch(r":?-+:?", celda) for celda in fila)]
    columnas = len(filas[0])
    # Reparte el ancho según el texto más largo de cada columna, con un mínimo razonable.
    pesos = [max(8, min(60, max(len(fila[i]) for fila in filas if i < len(fila))))
             for i in range(columnas)]
    anchos = [ANCHO * peso / sum(pesos) for peso in pesos]
    datos = [[Paragraph(marcar(celda), estilos["cabecera" if numero == 0 else "celda"])
              for celda in fila] for numero, fila in enumerate(filas)]
    objeto = Table(datos, colWidths=anchos, repeatRows=1)
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
for bloque in ORIGEN.read_text(encoding="utf-8").split("\n\n"):
    lineas = [linea for linea in bloque.strip().splitlines() if linea.strip()]
    if not lineas:
        continue
    primera = lineas[0]
    if primera.startswith("# "):
        elementos.append(Paragraph(marcar(primera[2:]), estilos["titulo"]))
    elif primera.startswith("## "):
        elementos.append(Paragraph(marcar(primera[3:]), estilos["seccion"]))
    elif primera.startswith("### "):
        elementos.append(Paragraph(marcar(primera[4:]), estilos["subseccion"]))
    elif all(linea.lstrip().startswith("|") for linea in lineas):
        elementos.append(tabla(lineas))
        elementos.append(Spacer(1, 7))
    elif all(linea.lstrip().startswith("- ") for linea in lineas):
        for linea in lineas:
            elementos.append(Paragraph(marcar(linea.lstrip()[2:]), estilos["lista"], bulletText="•"))
        elementos.append(Spacer(1, 4))
    else:
        elementos.append(Paragraph(marcar(" ".join(lineas)), estilos["texto"]))

SimpleDocTemplate(str(DESTINO), pagesize=A4, leftMargin=48, rightMargin=48, topMargin=48,
                  bottomMargin=48, title="Informe técnico — Pedro",
                  author="Proyecto Pedro (Infnet)").build(elementos)
print(DESTINO)
