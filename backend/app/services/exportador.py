"""Exportación de recursos (HU0021, HU0022, HU0023).

Convierte las secciones del editor a PDF, Word, Excel, HTML o TXT conservando
títulos, negritas, listas y tablas. Las tablas anchas ajustan el ancho de sus
columnas para no salirse de los márgenes (HU0022-2). Si el logo institucional
no está disponible se usa el nombre de la universidad en texto (HU0023-2).
"""
import base64
import io
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

from ..config import config
from .html_util import html_a_bloques, runs_a_texto
from .universidades import UNIVERSIDADES_PRIVADAS_LIMA

FORMATOS = {
    "pdf": ("application/pdf", "pdf"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "html": ("text/html; charset=utf-8", "html"),
    "txt": ("text/plain; charset=utf-8", "txt"),
}

AZUL = "0369A1"


class ErrorExportacion(Exception):
    pass


def _logo(clave: str | None = None) -> Path | None:
    """Obtiene el logo seleccionado y conserva el membrete predeterminado como respaldo."""
    if clave in UNIVERSIDADES_PRIVADAS_LIMA:
        cache = config.STORAGE_DIR / "logos" / f"{clave}-v2.png"
        if not cache.is_file():
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                dominio = UNIVERSIDADES_PRIVADAS_LIMA[clave]["dominio"]
                urls = [
                    UNIVERSIDADES_PRIVADAS_LIMA[clave]["logo_url"],
                    f"https://www.google.com/s2/favicons?domain={dominio}&sz=128",
                ]
                datos = None
                for url in urls:
                    try:
                        solicitud = Request(url, headers={"User-Agent": "EducaGen/1.0"})
                        with urlopen(solicitud, timeout=4) as respuesta:
                            datos = respuesta.read(2 * 1024 * 1024)
                        if datos:
                            break
                    except Exception:
                        continue
                if not datos:
                    raise ValueError("No se pudo recuperar el logo institucional")
                from PIL import Image

                imagen = Image.open(io.BytesIO(datos))
                imagen.convert("RGBA").save(cache, format="PNG")
            except Exception:
                pass
        if cache.is_file():
            return cache
    ruta = Path(config.MEMBRETE_LOGO)
    return ruta if ruta.is_file() else None


def _universidad(meta: dict) -> str:
    return meta.get("universidad_nombre") or config.UNIVERSIDAD_NOMBRE


def _secciones_visibles(secciones, incluir_ocultas):
    return [s for s in secciones if incluir_ocultas or not s.get("oculta")]


def _anchos(filas, total):
    """Ancho proporcional al contenido de cada columna, con mínimos y máximos."""
    ncol = max(len(f) for f in filas)
    largos = [0] * ncol
    for fila in filas:
        for i, (_, runs) in enumerate(fila):
            largos[i] = max(largos[i], min(60, len(runs_a_texto(runs)) or 1))
    largos = [max(8, l) for l in largos]
    suma = sum(largos)
    return [total * l / suma for l in largos]


def exportar(formato: str, titulo: str, secciones: list[dict], membrete: bool, incluir_ocultas: bool = True, meta: dict | None = None) -> tuple[bytes, str, str]:
    if formato not in FORMATOS:
        raise ErrorExportacion("Formato no admitido.")
    meta = meta or {}
    secciones = _secciones_visibles(secciones, incluir_ocultas)
    try:
        datos = {
            "pdf": _pdf, "docx": _docx, "xlsx": _xlsx, "html": _html, "txt": _txt,
        }[formato](titulo, secciones, membrete, meta)
    except ErrorExportacion:
        raise
    except Exception as e:  # HU0021-2
        raise ErrorExportacion(f"No se pudo convertir el documento a {formato.upper()}: {e}") from e
    mime, ext = FORMATOS[formato]
    return datos, mime, ext


# ---------------------------------------------------------------------------
# PDF (reportlab)
# ---------------------------------------------------------------------------
def _pdf(titulo, secciones, membrete, meta) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    margen_sup = 3.2 * cm if membrete else 2 * cm
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=margen_sup, bottomMargin=2 * cm, title=titulo)
    estilos = getSampleStyleSheet()
    azul = colors.HexColor("#" + AZUL)
    st_titulo = ParagraphStyle("t", parent=estilos["Title"], fontSize=17, textColor=colors.HexColor("#0f172a"), alignment=TA_LEFT, spaceAfter=4)
    st_meta = ParagraphStyle("m", parent=estilos["Normal"], fontSize=9, textColor=colors.HexColor("#475569"), spaceAfter=10)
    st_h3 = ParagraphStyle("h3", parent=estilos["Heading2"], fontSize=13, textColor=azul, spaceBefore=12, spaceAfter=6)
    st_h4 = ParagraphStyle("h4", parent=estilos["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4)
    st_p = ParagraphStyle("p", parent=estilos["Normal"], fontSize=10, leading=14, spaceAfter=6)
    st_celda = ParagraphStyle("c", parent=st_p, fontSize=8.5, leading=11, spaceAfter=0)
    st_celda_h = ParagraphStyle("ch", parent=st_celda, fontName="Helvetica-Bold", textColor=colors.white)

    def marcado(runs):
        partes = []
        for texto, b, i, u in runs:
            t = escape(texto).replace("\n", "<br/>")
            if u:
                t = f"<u>{t}</u>"
            if i:
                t = f"<i>{t}</i>"
            if b:
                t = f"<b>{t}</b>"
            partes.append(t)
        return "".join(partes)

    historia = [Paragraph(escape(titulo), st_titulo)]
    linea_meta = " | ".join(x for x in [meta.get("curso"), meta.get("docente"), datetime.now().strftime("%d/%m/%Y")] if x)
    historia.append(Paragraph(escape(linea_meta), st_meta))
    ancho_util = A4[0] - 4 * cm

    for s in secciones:
        historia.append(Paragraph(escape(s.get("titulo", "")), st_h3))
        for b in html_a_bloques(s.get("html", "")):
            if b[0] == "h":
                historia.append(Paragraph(marcado(b[2]), st_h4))
            elif b[0] == "p":
                historia.append(Paragraph(marcado(b[1]), st_p))
            elif b[0] == "lista":
                items = [ListItem(Paragraph(marcado(r), st_p), leftIndent=12) for r in b[2]]
                historia.append(ListFlowable(items, bulletType="1" if b[1] else "bullet", start="1" if b[1] else None, leftIndent=14, bulletFontSize=8))
            elif b[0] == "tabla":
                filas = b[1]
                ncol = max(len(f) for f in filas)
                datos = []
                for f in filas:
                    celdas = [Paragraph(marcado(r), st_celda_h if h else st_celda) for h, r in f]
                    celdas += [""] * (ncol - len(celdas))
                    datos.append(celdas)
                tabla = Table(datos, colWidths=_anchos([f + [(False, [])] * (ncol - len(f)) for f in filas], ancho_util), repeatRows=1 if filas[0][0][0] else 0)
                estilo = [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
                if filas[0][0][0]:
                    estilo.append(("BACKGROUND", (0, 0), (-1, 0), azul))
                tabla.setStyle(TableStyle(estilo))
                historia += [Spacer(1, 4), tabla, Spacer(1, 8)]

    logo = _logo(meta.get("universidad_clave")) if membrete else None

    def encabezado(canvas, _doc):
        canvas.saveState()
        if membrete:
            y = A4[1] - 1.6 * cm
            x = 2 * cm
            if logo:
                try:
                    canvas.drawImage(str(logo), x, y - 0.4 * cm, width=1.6 * cm, height=0.9 * cm, preserveAspectRatio=True, mask="auto")
                    x += 1.9 * cm
                except Exception:
                    pass
            canvas.setFont("Helvetica-Bold", 10)
            canvas.setFillColor(colors.HexColor("#0f172a"))
            canvas.drawString(x, y, _universidad(meta))
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#475569"))
            canvas.drawString(x, y - 0.4 * cm, meta.get("curso") or "")
            canvas.setStrokeColor(azul)
            canvas.setLineWidth(1)
            canvas.line(2 * cm, y - 0.75 * cm, A4[0] - 2 * cm, y - 0.75 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=encabezado, onLaterPages=encabezado)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Word (python-docx)
# ---------------------------------------------------------------------------
def _docx(titulo, secciones, membrete, meta) -> bytes:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2)
    sec.top_margin = Cm(2.5)
    estilo = doc.styles["Normal"]
    estilo.font.name = "Calibri"
    estilo.font.size = Pt(10.5)
    azul = RGBColor.from_string(AZUL)

    if membrete:
        cab = sec.header
        p = cab.paragraphs[0]
        logo = _logo(meta.get("universidad_clave"))
        if logo:
            try:
                p.add_run().add_picture(str(logo), height=Cm(0.9))
                p.add_run("   ")
            except Exception:
                pass
        r = p.add_run(_universidad(meta))
        r.bold = True
        r.font.size = Pt(10)
        if meta.get("curso"):
            r2 = cab.add_paragraph().add_run(meta["curso"])
            r2.font.size = Pt(8)
            r2.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    h = doc.add_heading(titulo, level=0)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
        run.font.size = Pt(20)
    linea_meta = " | ".join(x for x in [meta.get("curso"), meta.get("docente"), datetime.now().strftime("%d/%m/%Y")] if x)
    if linea_meta:
        doc.add_paragraph(linea_meta).runs[0].font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    def agregar_runs(parrafo, runs):
        for texto, b, i, u in runs:
            partes = texto.split("\n")
            for k, parte in enumerate(partes):
                run = parrafo.add_run(parte)
                run.bold, run.italic, run.underline = b, i, u
                if k < len(partes) - 1:
                    run.add_break()

    ancho_util = Cm(17)
    for s in secciones:
        hs = doc.add_heading(s.get("titulo", ""), level=1)
        for run in hs.runs:
            run.font.color.rgb = azul
        for b in html_a_bloques(s.get("html", "")):
            if b[0] == "h":
                agregar_runs(doc.add_heading(level=2), b[2])
            elif b[0] == "p":
                agregar_runs(doc.add_paragraph(), b[1])
            elif b[0] == "lista":
                for r in b[2]:
                    agregar_runs(doc.add_paragraph(style="List Number" if b[1] else "List Bullet"), r)
            elif b[0] == "tabla":
                filas = b[1]
                ncol = max(len(f) for f in filas)
                tabla = doc.add_table(rows=0, cols=ncol)
                tabla.style = "Table Grid"
                tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
                tabla.autofit = False
                anchos = _anchos([f + [(False, [])] * (ncol - len(f)) for f in filas], ancho_util)
                for f in filas:
                    celdas = tabla.add_row().cells
                    for j in range(ncol):
                        celdas[j].width = int(anchos[j])
                        if j < len(f):
                            es_h, runs = f[j]
                            par = celdas[j].paragraphs[0]
                            agregar_runs(par, runs)
                            for run in par.runs:
                                run.font.size = Pt(9)
                                if es_h:
                                    run.bold = True
                                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                            if es_h:
                                sombra = OxmlElement("w:shd")
                                sombra.set(qn("w:val"), "clear")
                                sombra.set(qn("w:fill"), AZUL)
                                celdas[j]._tc.get_or_add_tcPr().append(sombra)
                doc.add_paragraph()
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Excel (openpyxl)
# ---------------------------------------------------------------------------
def _xlsx(titulo, secciones, membrete, meta) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Recurso"
    ncol_max = 6
    for s in secciones:
        for b in html_a_bloques(s.get("html", "")):
            if b[0] == "tabla":
                ncol_max = max(ncol_max, max(len(f) for f in b[1]))
    fila = 1
    borde = Border(*(Side(style="thin", color="CBD5E1"),) * 4)
    envolver = Alignment(wrap_text=True, vertical="top")

    def fila_texto(texto, fuente=None, relleno=None, alto=None):
        nonlocal fila
        ws.cell(row=fila, column=1, value=texto).alignment = envolver
        if fuente:
            ws.cell(row=fila, column=1).font = fuente
        if relleno:
            ws.cell(row=fila, column=1).fill = relleno
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=ncol_max)
        lineas = max(1, len(texto) // (ncol_max * 18) + texto.count("\n") + 1)
        ws.row_dimensions[fila].height = alto or min(400, 15 * lineas)
        fila += 1

    if membrete:
        logo = _logo(meta.get("universidad_clave"))
        if logo:
            try:
                from openpyxl.drawing.image import Image as XLImage

                img = XLImage(str(logo))
                proporcion = 36 / img.height
                img.height, img.width = 36, int(img.width * proporcion)
                ws.add_image(img, "A1")
                ws.row_dimensions[1].height = 30
                ws.cell(row=1, column=2, value=_universidad(meta)).font = Font(bold=True, size=12)
                fila = 2
            except Exception:
                fila_texto(_universidad(meta), Font(bold=True, size=12))
        else:
            fila_texto(_universidad(meta), Font(bold=True, size=12))

    fila_texto(titulo, Font(bold=True, size=15), alto=24)
    linea_meta = " | ".join(x for x in [meta.get("curso"), meta.get("docente"), datetime.now().strftime("%d/%m/%Y")] if x)
    fila_texto(linea_meta, Font(size=9, color="475569"))
    fila += 1

    for s in secciones:
        fila_texto(s.get("titulo", ""), Font(bold=True, size=12, color="FFFFFF"), PatternFill("solid", fgColor=AZUL), alto=20)
        for b in html_a_bloques(s.get("html", "")):
            if b[0] == "h":
                fila_texto(runs_a_texto(b[2]), Font(bold=True))
            elif b[0] == "p":
                negrita = all(r[1] for r in b[1] if r[0].strip())
                fila_texto(runs_a_texto(b[1]), Font(bold=negrita))
            elif b[0] == "lista":
                for k, r in enumerate(b[2], 1):
                    prefijo = f"{k}. " if b[1] else "• "
                    fila_texto(prefijo + runs_a_texto(r))
            elif b[0] == "tabla":
                for f in b[1]:
                    alto = 15
                    for j, (es_h, runs) in enumerate(f, 1):
                        texto = runs_a_texto(runs)
                        c = ws.cell(row=fila, column=j, value=texto)
                        c.alignment = envolver
                        c.border = borde
                        if es_h:
                            c.font = Font(bold=True, color="FFFFFF")
                            c.fill = PatternFill("solid", fgColor="0EA5E9")
                        alto = max(alto, min(300, 15 * (len(texto) // 28 + 1)))
                    ws.row_dimensions[fila].height = alto
                    fila += 1
        fila += 1

    for j in range(1, ncol_max + 1):
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = 28
    ws.sheet_view.showGridLines = False
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# HTML y TXT
# ---------------------------------------------------------------------------
def _html(titulo, secciones, membrete, meta) -> bytes:
    cab = ""
    if membrete:
        logo = _logo(meta.get("universidad_clave"))
        img = ""
        if logo:
            img = f'<img src="data:image/png;base64,{base64.b64encode(logo.read_bytes()).decode()}" alt="" style="height:40px">'
        cab = f'<header class="membrete">{img}<div><strong>{escape(_universidad(meta))}</strong><br><small>{escape(meta.get("curso") or "")}</small></div></header>'
    cuerpo = "".join(f"<section><h2>{escape(s.get('titulo', ''))}</h2>{s.get('html', '')}</section>" for s in secciones)
    linea_meta = " | ".join(x for x in [meta.get("curso"), meta.get("docente"), datetime.now().strftime("%d/%m/%Y")] if x)
    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)}</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #0f172a; max-width: 820px; margin: 32px auto; padding: 0 20px; line-height: 1.55; }}
.membrete {{ display: flex; gap: 14px; align-items: center; border-bottom: 2px solid #{AZUL}; padding-bottom: 10px; margin-bottom: 24px; }}
h1 {{ font-size: 1.7rem; margin-bottom: 4px; }} .meta {{ color: #475569; font-size: .85rem; }}
h2 {{ color: #{AZUL}; font-size: 1.2rem; margin-top: 28px; }} h4 {{ margin-bottom: 4px; }}
table {{ width: 100%; border-collapse: collapse; table-layout: auto; margin: 10px 0; }}
th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; vertical-align: top; text-align: left; word-break: break-word; }}
th {{ background: #{AZUL}; color: #fff; }}
</style></head><body>{cab}<h1>{escape(titulo)}</h1><p class="meta">{escape(linea_meta)}</p>{cuerpo}</body></html>"""
    return html.encode("utf-8")


def _txt(titulo, secciones, membrete, meta) -> bytes:
    lineas = []
    if membrete:
        nombre_universidad = _universidad(meta)
        lineas += [nombre_universidad.upper(), "=" * len(nombre_universidad), ""]
    lineas += [titulo, "=" * len(titulo)]
    linea_meta = " | ".join(x for x in [meta.get("curso"), meta.get("docente"), datetime.now().strftime("%d/%m/%Y")] if x)
    lineas += [linea_meta, ""]
    for s in secciones:
        t = s.get("titulo", "")
        lineas += [t.upper(), "-" * len(t)]
        for b in html_a_bloques(s.get("html", "")):
            if b[0] == "h":
                lineas += ["", runs_a_texto(b[2])]
            elif b[0] == "p":
                lineas.append(runs_a_texto(b[1]))
            elif b[0] == "lista":
                for k, r in enumerate(b[2], 1):
                    lineas.append(f"  {k}. {runs_a_texto(r)}" if b[1] else f"  - {runs_a_texto(r)}")
            elif b[0] == "tabla":
                filas = [[runs_a_texto(r) for _, r in f] for f in b[1]]
                ncol = max(len(f) for f in filas)
                anchos = [min(40, max(len(f[j]) if j < len(f) else 0 for f in filas)) for j in range(ncol)]
                for f in filas:
                    lineas.append(" | ".join((f[j] if j < len(f) else "")[:40].ljust(anchos[j]) for j in range(ncol)))
        lineas.append("")
    return "\n".join(lineas).encode("utf-8")
