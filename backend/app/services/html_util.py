"""Utilidades para el HTML del editor.

- limpiar_html: deja solo el formato que admite el editor (HU0015-2) y protege
  contra HTML peligroso devuelto por el LLM.
- html_a_texto: texto plano (prompts, comparación de versiones, TXT).
- html_a_bloques: estructura intermedia usada por los exportadores (HU0022).
"""
from html import escape
from html.parser import HTMLParser

PERMITIDAS = {"p", "br", "strong", "em", "u", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td", "h3", "h4"}
EQUIVALENTES = {"b": "strong", "i": "em", "h1": "h3", "h2": "h3", "h5": "h4", "h6": "h4", "div": "p", "section": "p", "article": "p", "blockquote": "p"}
IGNORAR_CONTENIDO = {"script", "style", "head", "title", "iframe", "object", "noscript", "svg"}
VACIAS = {"br"}
BLOQUE = {"p", "h3", "h4", "li", "tr", "table", "ul", "ol"}


class _Limpiador(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.salida: list[str] = []
        self.pila: list[str] = []
        self.ignorando = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in IGNORAR_CONTENIDO:
            self.ignorando += 1
            return
        if self.ignorando:
            return
        tag = EQUIVALENTES.get(tag, tag)
        if tag not in PERMITIDAS:
            return
        if tag == "p" and "p" in self.pila:  # no anidar párrafos
            self._cerrar("p")
        if tag in VACIAS:
            self.salida.append(f"<{tag}>")
            return
        self.salida.append(f"<{tag}>")
        self.pila.append(tag)

    def handle_startendtag(self, tag, attrs):
        tag = EQUIVALENTES.get(tag.lower(), tag.lower())
        if not self.ignorando and tag in VACIAS:
            self.salida.append(f"<{tag}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in IGNORAR_CONTENIDO:
            self.ignorando = max(0, self.ignorando - 1)
            return
        if self.ignorando:
            return
        tag = EQUIVALENTES.get(tag, tag)
        if tag in PERMITIDAS and tag in self.pila:
            self._cerrar(tag)

    def _cerrar(self, tag):
        while self.pila:
            abierta = self.pila.pop()
            self.salida.append(f"</{abierta}>")
            if abierta == tag:
                break

    def handle_data(self, data):
        if not self.ignorando:
            self.salida.append(escape(data, quote=False))

    def resultado(self) -> str:
        while self.pila:
            self.salida.append(f"</{self.pila.pop()}>")
        return "".join(self.salida).strip()


def limpiar_html(html: str) -> str:
    if not html:
        return ""
    if "<" not in html:  # texto plano: un párrafo por bloque
        partes = [p.strip() for p in html.replace("\r", "").split("\n\n") if p.strip()]
        return "".join(f"<p>{escape(p).replace(chr(10), '<br>')}</p>" for p in partes)
    parser = _Limpiador()
    parser.feed(html)
    parser.close()
    return parser.resultado()


# ---------------------------------------------------------------------------
# Bloques para exportación
# ---------------------------------------------------------------------------
class _Bloques(HTMLParser):
    """Convierte HTML limpio en bloques: ('h', nivel, runs) | ('p', runs) | ('lista', ordenada, [runs]) | ('tabla', filas)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bloques: list = []
        self.runs: list = []
        self.estilo = {"strong": 0, "em": 0, "u": 0}
        self.lista = None  # (ordenada, items)
        self.tabla = None  # filas
        self.fila = None
        self.celda = None  # (es_encabezado, runs)
        self.encabezado = None

    def _flush(self, tipo="p", nivel=None):
        texto = "".join(r[0] for r in self.runs).strip()
        if texto:
            if tipo == "h":
                self.bloques.append(("h", nivel, self.runs))
            else:
                self.bloques.append(("p", self.runs))
        self.runs = []

    def handle_starttag(self, tag, attrs):
        tag = EQUIVALENTES.get(tag.lower(), tag.lower())
        if tag in self.estilo:
            self.estilo[tag] += 1
        elif tag == "br":
            self.runs.append(("\n", False, False, False))
        elif tag in ("p", "h3", "h4"):
            if self.celda is None and self.lista is None:
                self._flush()
        elif tag in ("ul", "ol"):
            self._flush()
            self.lista = (tag == "ol", [])
        elif tag == "li":
            self.runs = []
        elif tag == "table":
            self._flush()
            self.tabla = []
        elif tag == "tr" and self.tabla is not None:
            self.fila = []
        elif tag in ("td", "th") and self.fila is not None:
            self.runs = []
            self.encabezado = tag == "th"

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = EQUIVALENTES.get(tag.lower(), tag.lower())
        if tag in self.estilo:
            self.estilo[tag] = max(0, self.estilo[tag] - 1)
        elif tag in ("h3", "h4") and self.celda is None and self.lista is None:
            self._flush("h", 3 if tag == "h3" else 4)
        elif tag == "p" and self.fila is None and self.lista is None:
            self._flush()
        elif tag == "p" and (self.fila is not None or self.lista is not None):
            self.runs.append(("\n", False, False, False))
        elif tag == "li" and self.lista is not None:
            self.lista[1].append(_recortar(self.runs))
            self.runs = []
        elif tag in ("ul", "ol") and self.lista is not None:
            if self.lista[1]:
                self.bloques.append(("lista", self.lista[0], self.lista[1]))
            self.lista = None
        elif tag in ("td", "th") and self.fila is not None:
            self.fila.append((bool(self.encabezado), _recortar(self.runs)))
            self.runs = []
        elif tag == "tr" and self.tabla is not None and self.fila is not None:
            if self.fila:
                self.tabla.append(self.fila)
            self.fila = None
        elif tag == "table" and self.tabla is not None:
            if self.tabla:
                self.bloques.append(("tabla", self.tabla))
            self.tabla = None

    def handle_data(self, data):
        if not data:
            return
        if self.fila is None and self.lista is None and not data.strip() and not self.runs:
            return
        self.runs.append((data, self.estilo["strong"] > 0, self.estilo["em"] > 0, self.estilo["u"] > 0))

    def resultado(self):
        self._flush()
        return self.bloques


def _recortar(runs):
    runs = list(runs)
    while runs and not runs[-1][0].strip():
        runs.pop()
    while runs and not runs[0][0].strip():
        runs.pop(0)
    return runs


def html_a_bloques(html: str) -> list:
    parser = _Bloques()
    parser.feed(limpiar_html(html))
    parser.close()
    return parser.resultado()


def runs_a_texto(runs) -> str:
    return " ".join("".join(r[0] for r in runs).split()) if runs else ""


def html_a_texto(html: str) -> str:
    lineas = []
    for bloque in html_a_bloques(html):
        if bloque[0] in ("h", "p"):
            lineas.append(runs_a_texto(bloque[-1]))
        elif bloque[0] == "lista":
            for i, item in enumerate(bloque[2], 1):
                lineas.append(f"{i}. {runs_a_texto(item)}" if bloque[1] else f"- {runs_a_texto(item)}")
        elif bloque[0] == "tabla":
            for fila in bloque[1]:
                lineas.append(" | ".join(runs_a_texto(c[1]) for c in fila))
    return "\n".join(lineas)
