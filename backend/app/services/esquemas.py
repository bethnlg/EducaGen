"""Esquemas de salida de cada tipo de recurso (HU0034), conversión del JSON
del LLM a secciones del editor y verificación de secciones obligatorias (HU0024).
"""
import re
import unicodedata
import uuid
from html import escape

from .html_util import html_a_texto

TIPOS = {
    "silabo": "Sílabo",
    "rubrica": "Rúbrica",
    "examen": "Examen",
    "caso": "Caso de estudio",
}

# Secciones obligatorias según el formato institucional: (clave, título, alias para reconocerla)
SECCIONES_OBLIGATORIAS = {
    "silabo": [
        ("datos_generales", "Datos generales", ["datos generales", "informacion general"]),
        ("sumilla", "Sumilla", ["sumilla", "descripcion del curso"]),
        ("competencias", "Competencias", ["competencia", "logro"]),
        ("unidades", "Unidades de aprendizaje", ["unidad"]),
        ("metodologia", "Metodología", ["metodologia", "estrategias didacticas"]),
        ("evaluacion", "Sistema de evaluación", ["evaluacion", "calificacion"]),
        ("bibliografia", "Bibliografía", ["bibliografia", "referencias"]),
    ],
    "rubrica": [
        ("descripcion", "Descripción de la rúbrica", ["descripcion", "proposito"]),
        ("niveles", "Niveles de desempeño", ["niveles", "escala"]),
        ("criterios", "Matriz de evaluación", ["matriz", "criterios"]),
        ("puntaje", "Puntaje total", ["puntaje", "nota"]),
    ],
    "examen": [
        ("instrucciones", "Instrucciones", ["instrucciones", "indicaciones"]),
        ("opcion_multiple", "Preguntas de opción múltiple", ["opcion multiple", "alternativas", "seleccion multiple"]),
        ("desarrollo", "Preguntas de desarrollo", ["desarrollo", "preguntas abiertas"]),
        ("clave", "Clave de respuestas", ["clave", "solucionario", "respuestas"]),
    ],
    "caso": [
        ("contexto", "Contexto de la empresa", ["contexto", "empresa", "organizacion"]),
        ("narrativa", "Descripción del caso", ["descripcion del caso", "narrativa", "el caso"]),
        ("problema", "Problema a analizar", ["problema", "desafio"]),
        ("preguntas", "Preguntas de discusión", ["preguntas", "discusion"]),
    ],
}

# Estructura JSON que debe devolver el LLM (se envía en el prompt)
ESQUEMAS_JSON = {
    "silabo": {
        "titulo": "string",
        "datos_generales": {"curso": "string", "carrera": "string", "ciclo": "string", "semanas": "number", "creditos": "number", "modalidad": "string"},
        "sumilla": "string (un párrafo)",
        "competencias": ["string"],
        "unidades": [{"numero": "number", "titulo": "string", "semanas": "string (ej. 1-4)", "resultado_aprendizaje": "string", "contenidos": ["string"]}],
        "metodologia": "string",
        "evaluacion": [{"instrumento": "string", "semana": "string", "peso": "number (porcentaje, suman 100)"}],
        "bibliografia": ["string en formato APA 7"],
    },
    "rubrica": {
        "titulo": "string",
        "descripcion": "string",
        "nota_maxima": 20,
        "niveles": [{"nombre": "string", "puntaje": "number"}],
        "criterios": [{"nombre": "string", "peso": "number (porcentaje, suman 100)", "descriptores": ["string, uno por nivel y en el mismo orden"]}],
    },
    "examen": {
        "titulo": "string",
        "instrucciones": "string",
        "preguntas_opcion_multiple": [{"enunciado": "string", "opciones": ["string x4"], "respuesta": "letra A-D", "puntaje": "number"}],
        "preguntas_desarrollo": [{"enunciado": "string", "puntaje": "number", "respuesta_esperada": "string"}],
    },
    "caso": {
        "titulo": "string",
        "empresa": {"nombre": "string", "sector": "string", "descripcion": "string"},
        "narrativa": "string (2 a 4 párrafos separados por línea en blanco)",
        "problema": "string",
        "datos_clave": ["string"],
        "preguntas_discusion": ["string x4"],
    },
}

CLAVES_REQUERIDAS = {
    "silabo": ["titulo", "datos_generales", "sumilla", "competencias", "unidades", "metodologia", "evaluacion", "bibliografia"],
    "rubrica": ["titulo", "descripcion", "niveles", "criterios"],
    "examen": ["titulo", "instrucciones", "preguntas_opcion_multiple", "preguntas_desarrollo"],
    "caso": ["titulo", "empresa", "narrativa", "problema", "preguntas_discusion"],
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "").lower()
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).strip()


def validar_json(tipo: str, datos) -> list[str]:
    """Devuelve la lista de claves faltantes o vacías (HU0034-2)."""
    if not isinstance(datos, dict):
        return CLAVES_REQUERIDAS[tipo]
    faltantes = [c for c in CLAVES_REQUERIDAS[tipo] if not datos.get(c)]
    if tipo == "caso" and isinstance(datos.get("preguntas_discusion"), list) and len(datos["preguntas_discusion"]) < 4:
        faltantes.append("preguntas_discusion (se requieren 4)")
    if tipo == "rubrica":
        for c in datos.get("criterios") or []:
            if not isinstance(c, dict) or not c.get("descriptores"):
                faltantes.append("descriptores de criterios")
                break
    return faltantes


def _id() -> str:
    return "s" + uuid.uuid4().hex[:8]


def _p(texto) -> str:
    texto = str(texto or "").strip()
    if not texto:
        return ""
    return "".join(f"<p>{escape(par.strip())}</p>" for par in texto.split("\n\n") if par.strip())


def _ul(items, ordenada=False) -> str:
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return ""
    tag = "ol" if ordenada else "ul"
    return f"<{tag}>" + "".join(f"<li>{escape(str(i))}</li>" for i in items) + f"</{tag}>"


def _tabla(encabezados, filas) -> str:
    cab = "".join(f"<th>{escape(str(h))}</th>" for h in encabezados)
    cuerpo = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in fila) + "</tr>" for fila in filas)
    return f"<table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table>"


def _seccion(clave, titulo, html, **extra) -> dict:
    return {"id": _id(), "clave": clave, "titulo": titulo, "html": html, **extra}


def json_a_secciones(tipo: str, d: dict) -> list[dict]:
    """Convierte la salida estructurada del LLM en secciones editables."""
    if tipo == "silabo":
        dg = d.get("datos_generales") or {}
        filas = [[k.replace("_", " ").capitalize(), v] for k, v in dg.items() if v not in (None, "")]
        unidades = []
        for u in d.get("unidades") or []:
            unidades.append(
                f"<h4>Unidad {escape(str(u.get('numero', '')))}: {escape(str(u.get('titulo', '')))}</h4>"
                f"<p><strong>Semanas:</strong> {escape(str(u.get('semanas', '')))}</p>"
                f"<p><strong>Resultado de aprendizaje:</strong> {escape(str(u.get('resultado_aprendizaje', '')))}</p>"
                + _ul(u.get("contenidos"))
            )
        evaluacion = d.get("evaluacion") or []
        return [
            _seccion("datos_generales", "Datos generales", _tabla(["Campo", "Detalle"], filas)),
            _seccion("sumilla", "Sumilla", _p(d.get("sumilla"))),
            _seccion("competencias", "Competencias", _ul(d.get("competencias"))),
            _seccion("unidades", "Unidades de aprendizaje", "".join(unidades)),
            _seccion("metodologia", "Metodología", _p(d.get("metodologia"))),
            _seccion("evaluacion", "Sistema de evaluación", _tabla(
                ["Instrumento", "Semana", "Peso (%)"],
                [[e.get("instrumento", ""), e.get("semana", ""), e.get("peso", "")] for e in evaluacion],
            )),
            _seccion("bibliografia", "Bibliografía", _ul(d.get("bibliografia"))),
        ]

    if tipo == "rubrica":
        niveles = d.get("niveles") or []
        criterios = d.get("criterios") or []
        nombres_niveles = [f"{n.get('nombre', '')} ({n.get('puntaje', '')})" for n in niveles]
        filas = []
        for c in criterios:
            desc = list(c.get("descriptores") or [])
            desc += [""] * (len(niveles) - len(desc))
            filas.append([f"{c.get('nombre', '')} ({c.get('peso', '')}%)"] + desc[: len(niveles)])
        nota = d.get("nota_maxima", 20)
        suma = sum(float(c.get("peso") or 0) for c in criterios)
        return [
            _seccion("descripcion", "Descripción de la rúbrica", _p(d.get("descripcion"))),
            _seccion("niveles", "Niveles de desempeño", _ul([f"{n.get('nombre', '')}: {n.get('puntaje', '')} puntos" for n in niveles])),
            _seccion("criterios", "Matriz de evaluación", _tabla(["Criterio"] + nombres_niveles, filas)),
            _seccion("puntaje", "Puntaje total", _p(
                f"La nota máxima es {nota} puntos. Los pesos de los criterios suman {suma:g} %. "
                f"La nota final se obtiene multiplicando el puntaje del nivel alcanzado en cada criterio por su peso."
            )),
        ]

    if tipo == "examen":
        om = d.get("preguntas_opcion_multiple") or []
        de = d.get("preguntas_desarrollo") or []
        letras = "ABCDEFG"
        html_om = ""
        for i, q in enumerate(om, 1):
            opciones = "".join(f"<li>{letras[j]}) {escape(str(o))}</li>" for j, o in enumerate(q.get("opciones") or []))
            html_om += f"<p><strong>{i}. {escape(str(q.get('enunciado', '')))}</strong> ({escape(str(q.get('puntaje', 1)))} pts)</p><ul>{opciones}</ul>"
        inicio = len(om)
        html_de = "".join(
            f"<p><strong>{inicio + i}. {escape(str(q.get('enunciado', '')))}</strong> ({escape(str(q.get('puntaje', '')))} pts)</p>"
            for i, q in enumerate(de, 1)
        )
        filas = [[str(i), q.get("respuesta", "")] for i, q in enumerate(om, 1)]
        filas += [[str(inicio + i), q.get("respuesta_esperada", "")] for i, q in enumerate(de, 1)]
        return [
            _seccion("instrucciones", "Instrucciones", _p(d.get("instrucciones"))),
            _seccion("opcion_multiple", "Preguntas de opción múltiple", html_om),
            _seccion("desarrollo", "Preguntas de desarrollo", html_de),
            _seccion("clave", "Clave de respuestas", _tabla(["Pregunta", "Respuesta"], filas), oculta=True),
        ]

    # caso de estudio
    emp = d.get("empresa") or {}
    contexto = (
        f"<p><strong>Empresa:</strong> {escape(str(emp.get('nombre', '')))}</p>"
        f"<p><strong>Sector:</strong> {escape(str(emp.get('sector', '')))}</p>" + _p(emp.get("descripcion"))
    )
    narrativa = _p(d.get("narrativa"))
    if d.get("datos_clave"):
        narrativa += "<h4>Datos clave</h4>" + _ul(d.get("datos_clave"))
    return [
        _seccion("contexto", "Contexto de la empresa", contexto),
        _seccion("narrativa", "Descripción del caso", narrativa),
        _seccion("problema", "Problema a analizar", _p(d.get("problema"))),
        _seccion("preguntas", "Preguntas de discusión", _ul(d.get("preguntas_discusion"), ordenada=True)),
    ]


def verificar_conformidad(tipo: str, secciones: list[dict]) -> dict:
    """HU0024: revisa que existan todas las secciones obligatorias y que no estén vacías."""
    obligatorias = SECCIONES_OBLIGATORIAS.get(tipo, [])
    presentes = []
    faltantes = []
    for clave, titulo, alias in obligatorias:
        encontrada = False
        for s in secciones or []:
            if not html_a_texto(s.get("html", "")).strip():
                continue
            t = normalizar(s.get("titulo", ""))
            if s.get("clave") == clave or any(a in t for a in alias):
                encontrada = True
                break
        (presentes if encontrada else faltantes).append(titulo)
    total = len(obligatorias) or 1
    return {
        "conforme": not faltantes,
        "porcentaje": round(len(presentes) * 100 / total),
        "presentes": len(presentes),
        "total": len(obligatorias),
        "faltantes": faltantes,
    }


def contenido_a_texto(contenido: dict) -> str:
    partes = []
    for s in (contenido or {}).get("secciones", []):
        partes.append(s.get("titulo", ""))
        partes.append(html_a_texto(s.get("html", "")))
    return "\n".join(p for p in partes if p)
