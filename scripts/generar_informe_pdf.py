"""Convierte el informe Markdown sencillo a un PDF legible y reproducible."""
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

ROOT = Path(__file__).resolve().parents[1]
ORIGEN = ROOT / "docs/informe.md"
DESTINO = ROOT / "docs/informe.pdf"
FUENTE = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
if FUENTE.is_file():
    pdfmetrics.registerFont(TTFont("DejaVu", str(FUENTE)))
    font = "DejaVu"
else:
    font = "Helvetica"

estilos = {
    "titulo": ParagraphStyle("titulo", fontName=font, fontSize=16, leading=21,
                              textColor=colors.HexColor("#283963"), spaceAfter=13),
    "seccion": ParagraphStyle("seccion", fontName=font, fontSize=11, leading=16,
                               textColor=colors.HexColor("#283963"), spaceBefore=11, spaceAfter=6),
    "texto": ParagraphStyle("texto", fontName=font, fontSize=8.8, leading=14,
                             alignment=TA_LEFT, spaceAfter=7),
}

elementos = []
for bloque in ORIGEN.read_text(encoding="utf-8").split("\n\n"):
    texto = bloque.strip()
    if not texto:
        continue
    if texto.startswith("# "):
        estilo, texto = "titulo", texto[2:]
    elif texto.startswith("## "):
        estilo, texto = "seccion", texto[3:]
    else:
        estilo = "texto"
    texto = escape(texto).replace("**", "").replace("\n", "<br/>")
    elementos.append(Paragraph(texto, estilos[estilo]))
    elementos.append(Spacer(1, 3))

SimpleDocTemplate(str(DESTINO), pagesize=A4, leftMargin=48, rightMargin=48,
                  topMargin=48, bottomMargin=48).build(elementos)
print(DESTINO)
