"""Converte um documento Markdown do projeto em PDF.

Admite um subconjunto de Markdown: títulos (# a #####), parágrafos, listas com hífen, tabelas
com barras, **negrito**, blocos de código entre cercas (```) e imagens em um bloco próprio
(![legenda](caminho), com o caminho relativo ao arquivo Markdown). Não executa nada.

Há dois estilos:
- sem argumentos, gera o relatório de entrega (docs/relatorio.md) com aparência de documento
  comum: página carta, letra tipo Arial, títulos numerados em preto e texto justificado. Grava
  também a cópia com o nome de arquivo que o enunciado exige
  (nome_sobrenome_ai-agents_langchain-agents.pdf);
- com `<origem.md> <destino.pdf> [título] [largura da página em cm] [escala da letra]`, gera os
  outros documentos (guias e roteiros) com o estilo compacto de cartilha.
"""
import re
import shutil
import sys
import textwrap
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle, XPreformatted)

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTO = len(sys.argv) <= 2  # o relatório de entrega usa o estilo de documento comum
ORIGEM = Path(sys.argv[1]).resolve() if not DOCUMENTO else ROOT / "docs/relatorio.md"
DESTINO = Path(sys.argv[2]).resolve() if not DOCUMENTO else ROOT / "docs/relatorio.pdf"
TITULO = sys.argv[3] if len(sys.argv) > 3 else "Relatório Agentes Cognitivos com LangChain"
# Cópia do relatório com o nome exigido pelo enunciado; só é gravada na execução sem argumentos.
ENTREGA = ROOT / "docs/efrain_colmenares_ai-agents_langchain-agents.pdf" if DOCUMENTO else None
LARGURA_CM = float(sys.argv[4]) if len(sys.argv) > 4 else None
ESCALA = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0


def registrar(nome: str, pasta: str, arquivos: dict[str, str]) -> bool:
    """Registra uma família de fontes TrueType; devolve False se algum arquivo faltar."""
    caminhos = {estilo: Path(pasta) / arquivo for estilo, arquivo in arquivos.items()}
    if not all(caminho.is_file() for caminho in caminhos.values()):
        return False
    for estilo, caminho in caminhos.items():
        pdfmetrics.registerFont(TTFont(f"{nome}-{estilo}", str(caminho)))
    pdfmetrics.registerFontFamily(
        nome, normal=f"{nome}-normal", bold=f"{nome}-negrito",
        italic=f"{nome}-italico" if "italico" in caminhos else f"{nome}-normal",
        boldItalic=f"{nome}-negrito-italico" if "negrito-italico" in caminhos else f"{nome}-negrito")
    return True


if DOCUMENTO:
    # Liberation Sans tem as mesmas medidas da Arial; sem ela, usa-se a Helvetica do próprio PDF.
    if registrar("Texto", "/usr/share/fonts/truetype/liberation", {
            "normal": "LiberationSans-Regular.ttf", "negrito": "LiberationSans-Bold.ttf",
            "italico": "LiberationSans-Italic.ttf", "negrito-italico": "LiberationSans-BoldItalic.ttf"}):
        font, font_negrito = "Texto-normal", "Texto-negrito"
    else:
        font, font_negrito = "Helvetica", "Helvetica-Bold"
    mono = "Mono-normal" if registrar("Mono", "/usr/share/fonts/truetype/liberation", {
        "normal": "LiberationMono-Regular.ttf", "negrito": "LiberationMono-Bold.ttf"}) else "Courier"
    PAGINA, MARGEM = letter, 72
    COR_TITULO, COR_CABECALHO, COR_GRADE = colors.black, colors.HexColor("#e9e9e9"), colors.HexColor("#b5b5b5")
    estilos = {
        "titulo": ParagraphStyle("titulo", fontName=font, fontSize=20, leading=34, alignment=TA_CENTER,
                                 spaceAfter=18),
        "secao": ParagraphStyle("secao", fontName=font, fontSize=16, leading=22, spaceBefore=24,
                                spaceAfter=10, keepWithNext=1),
        "subsecao": ParagraphStyle("subsecao", fontName=font_negrito, fontSize=12.5, leading=18,
                                   spaceBefore=18, spaceAfter=6, keepWithNext=1),
        "item": ParagraphStyle("item", fontName=font_negrito, fontSize=11, leading=17, leftIndent=18,
                               spaceBefore=10, spaceAfter=3, keepWithNext=1),
        "rotulo": ParagraphStyle("rotulo", fontName=font, fontSize=12, leading=18, spaceBefore=16,
                                 spaceAfter=4, keepWithNext=1),
        "texto": ParagraphStyle("texto", fontName=font, fontSize=11, leading=19, alignment=TA_JUSTIFY,
                                firstLineIndent=30, spaceAfter=8),
        "lista": ParagraphStyle("lista", fontName=font, fontSize=11, leading=18, alignment=TA_JUSTIFY,
                                leftIndent=42, bulletIndent=24, spaceAfter=4),
        "celula": ParagraphStyle("celula", fontName=font, fontSize=9.5, leading=13),
        "cabecalho": ParagraphStyle("cabecalho", fontName=font_negrito, fontSize=9.5, leading=13),
        "legenda": ParagraphStyle("legenda", fontName=font, fontSize=9.5, leading=13, alignment=TA_CENTER,
                                  textColor=colors.HexColor("#555555"), spaceBefore=4, spaceAfter=10),
        "codigo": ParagraphStyle("codigo", fontName=mono, fontSize=7.8, leading=10.6,
                                 backColor=colors.HexColor("#f4f4f4"), borderPadding=7,
                                 leftIndent=7, rightIndent=7, spaceBefore=10, spaceAfter=16),
    }
    # O parágrafo que descreve uma evidência não se separa da captura que vem depois dele.
    estilos["texto_evidencia"] = ParagraphStyle("texto_evidencia", parent=estilos["texto"], keepWithNext=1)
    FUNDO_LINHAS = [colors.white, colors.white]
    COLUNAS_CODIGO = 92
else:
    FONTE = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    NEGRITO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if FONTE.is_file() and NEGRITO.is_file():
        pdfmetrics.registerFont(TTFont("DejaVu", str(FONTE)))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(NEGRITO)))
        pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold")
        font, font_negrito = "DejaVu", "DejaVu-Bold"
    else:
        font, font_negrito = "Helvetica", "Helvetica-Bold"
    mono = "Courier"
    AZUL = colors.HexColor("#283963")
    PAGINA = A4 if LARGURA_CM is None else (LARGURA_CM * cm, A4[1])
    MARGEM = 48 if LARGURA_CM is None else 30
    COR_TITULO, COR_CABECALHO, COR_GRADE = AZUL, AZUL, colors.HexColor("#b8bfd0")
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
        "legenda": ParagraphStyle("legenda", fontName=font, fontSize=7.6, leading=10.5,
                                  textColor=colors.HexColor("#56627a"), spaceBefore=4, spaceAfter=10),
        "codigo": ParagraphStyle("codigo", fontName=mono, fontSize=7, leading=9.5,
                                 backColor=colors.HexColor("#f3f5fa"), borderPadding=5,
                                 leftIndent=5, rightIndent=5, spaceBefore=6, spaceAfter=10),
    }
    estilos["item"] = estilos["rotulo"] = estilos["subsecao"]
    estilos["texto_evidencia"] = estilos["texto"]
    FUNDO_LINHAS = [colors.white, colors.HexColor("#f3f5fa")]
    COLUNAS_CODIGO = 100
    if ESCALA != 1.0:
        for estilo in {id(e): e for e in estilos.values()}.values():
            estilo.fontSize *= ESCALA
            estilo.leading *= ESCALA
LARGURA = PAGINA[0] - 2 * MARGEM
TITULOS = [("##### ", "rotulo"), ("#### ", "item"), ("### ", "subsecao"), ("## ", "secao"), ("# ", "titulo")]


def marcar(texto: str) -> str:
    """Escapa o texto e converte **negrito** e `código` para a marcação do ReportLab.

    No estilo de documento converte também *itálico*; os outros documentos usam o asterisco
    em nomes de arquivos e de variáveis, e lá ele fica como está.
    """
    texto = escape(texto)
    if DOCUMENTO:
        texto = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", texto)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    if DOCUMENTO:
        texto = re.sub(r"\*(.+?)\*", r"<i>\1</i>", texto)
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
    lado, alto = (5, 4) if DOCUMENTO else (4, 3)
    objeto.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR_CABECALHO),
        ("GRID", (0, 0), (-1, -1), 0.4, COR_GRADE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), FUNDO_LINHAS),
        ("LEFTPADDING", (0, 0), (-1, -1), lado), ("RIGHTPADDING", (0, 0), (-1, -1), lado),
        ("TOPPADDING", (0, 0), (-1, -1), alto), ("BOTTOMPADDING", (0, 0), (-1, -1), alto),
    ]))
    return objeto


def figura(legenda: str, caminho: str) -> list:
    """Imagem ajustada à largura do texto; a legenda, se houver, fica embaixo e não se separa.

    Sem legenda devolve a imagem solta, para que o título e o parágrafo anteriores possam
    ficar na mesma página que ela.
    """
    arquivo = (ORIGEM.parent / caminho).resolve()
    largura_px, altura_px = ImageReader(str(arquivo)).getSize()
    largura = LARGURA
    altura = largura * altura_px / largura_px
    limite = (PAGINA[1] - 2 * MARGEM) * 0.82
    if altura > limite:
        largura, altura = largura * limite / altura, limite
    imagem = Image(str(arquivo), width=largura, height=altura)
    imagem.hAlign = "CENTER"
    if not legenda:
        return [imagem, Spacer(1, 12)]
    return [KeepTogether([imagem, Paragraph(marcar(legenda), estilos["legenda"])])]


def codigo(texto: str) -> XPreformatted:
    """Bloco de código ou de log: letra de largura fixa, com as linhas longas quebradas."""
    linhas = []
    for linha in texto.rstrip("\n").split("\n"):
        linhas.extend(textwrap.wrap(linha, COLUNAS_CODIGO, subsequent_indent="    ",
                                    replace_whitespace=False, drop_whitespace=False) or [""])
    return XPreformatted(escape("\n".join(linhas)), estilos["codigo"])


def blocos(texto: str) -> list:
    elementos = []
    depois_de_rotulo = False
    for bloco in texto.split("\n\n"):
        linhas = [linha for linha in bloco.strip().splitlines() if linha.strip()]
        if not linhas:
            continue
        primeira = linhas[0]
        nivel = next((estilo for marca, estilo in TITULOS if primeira.startswith(marca)), None)
        era_rotulo, depois_de_rotulo = depois_de_rotulo, nivel == "rotulo"
        if nivel:
            elementos.append(Paragraph(marcar(primeira.split(" ", 1)[1]), estilos[nivel]))
        elif len(linhas) == 1 and (imagem := re.fullmatch(r"!\[(.*?)\]\((.+?)\)", primeira.strip())):
            elementos.extend(figura(imagem[1], imagem[2]))
        elif all(linha.lstrip().startswith("|") for linha in linhas):
            elementos.append(tabela(linhas))
            elementos.append(Spacer(1, 12 if DOCUMENTO else 7))
        elif all(linha.lstrip().startswith("- ") for linha in linhas):
            for linha in linhas:
                elementos.append(Paragraph(marcar(linha.lstrip()[2:]), estilos["lista"], bulletText="•"))
            elementos.append(Spacer(1, 4))
        else:
            elementos.append(Paragraph(marcar(" ".join(linhas)),
                                       estilos["texto_evidencia" if era_rotulo else "texto"]))
    return elementos


elementos = []
# As cercas de código são separadas primeiro: dentro delas pode haver linhas em branco.
partes = re.split(r"(?ms)^```[a-z]*\n(.*?)^```[ \t]*$", ORIGEM.read_text(encoding="utf-8"))
for numero, parte in enumerate(partes):
    elementos.extend([codigo(parte)] if numero % 2 else blocos(parte))

SimpleDocTemplate(str(DESTINO), pagesize=PAGINA, leftMargin=MARGEM, rightMargin=MARGEM,
                  topMargin=MARGEM, bottomMargin=MARGEM, title=TITULO,
                  author="Efrain Colmenares Guerrero" if DOCUMENTO else "Projeto Pedro (Infnet)").build(elementos)
print(DESTINO)
if ENTREGA:
    shutil.copyfile(DESTINO, ENTREGA)
    print(ENTREGA)
