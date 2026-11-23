"""Proveedor de demostración.

Permite ejecutar y probar la aplicación sin claves de Gemini ni de Claude:
genera contenido de plantilla a partir de los datos del docente y respeta
el mismo contrato (streaming, JSON, marcador de cambios) que los LLM reales.
"""
import asyncio
import json
import random
import re
from datetime import date
from html import escape
from typing import AsyncIterator

from .base import Proveedor, ProveedorError, Solicitud, Uso, estimar_tokens

MARCADOR = "<<<CAMBIOS>>>"


def _cap(t: str) -> str:
    t = (t or "").strip()
    return t[:1].upper() + t[1:] if t else t


class DemoProveedor(Proveedor):
    def __init__(self, nombre: str = "demo", fallar: bool = False):
        self.nombre = nombre
        self.modelo = "plantillas-locales"
        self.fallar = fallar

    async def stream(self, sol: Solicitud, uso: Uso) -> AsyncIterator[str]:
        uso.proveedor, uso.modelo = self.nombre, self.modelo
        if self.fallar:
            await asyncio.sleep(0.2)
            raise ProveedorError(f"{self.nombre}: servicio no disponible (falla simulada)")
        texto = self._responder(sol)
        uso.tokens_entrada = estimar_tokens(sol.sistema + sol.prompt)
        uso.tokens_salida = estimar_tokens(texto)
        paso = 24
        for i in range(0, len(texto), paso):
            await asyncio.sleep(0.012)
            yield texto[i : i + paso]

    # ------------------------------------------------------------------
    def _responder(self, sol: Solicitud) -> str:
        ctx = sol.contexto or {}
        if sol.operacion == "generacion":
            return json.dumps(generar_recurso(ctx.get("tipo", "silabo"), ctx.get("params", {})), ensure_ascii=False)
        if sol.operacion == "regeneracion":
            return regenerar_bloque(ctx.get("bloque_texto", ""), ctx.get("instruccion", ""))
        if sol.operacion == "calificacion":
            nota_max = float(ctx.get("nota_maxima", 20))
            largo = len((ctx.get("respuesta") or "").split())
            nota = round(min(nota_max, max(nota_max * 0.45, nota_max * (0.5 + min(largo, 250) / 500))), 1)
            return json.dumps({"nota": nota, "justificacion": "Calificación estimada en modo demostración según la extensión y cobertura de la respuesta frente a los criterios."}, ensure_ascii=False)
        return responder_asistente(ctx)


# ----------------------------------------------------------------------
# Generación de recursos
# ----------------------------------------------------------------------
def generar_recurso(tipo: str, p: dict) -> dict:
    curso = p.get("curso") or "Curso"
    temas = p.get("temas") or ["Fundamentos", "Aplicaciones", "Evaluación integral"]
    carrera = p.get("carrera") or "Ingeniería de Software"
    anio = date.today().year

    if tipo == "silabo":
        semanas = int(p.get("semanas") or 16)
        n = max(2, min(len(temas), 6))
        temas = (temas * 2)[:n]
        tramo = max(1, semanas // n)
        unidades = []
        for i, t in enumerate(temas):
            ini = i * tramo + 1
            fin = semanas if i == n - 1 else (i + 1) * tramo
            unidades.append({
                "numero": i + 1,
                "titulo": _cap(t),
                "semanas": f"{ini}-{fin}",
                "resultado_aprendizaje": f"Al finalizar la unidad, el estudiante aplica {t.lower()} para resolver problemas propios de {curso} con criterio técnico.",
                "contenidos": [f"Conceptos base de {t.lower()}", f"Casos y ejercicios guiados de {t.lower()}", f"Laboratorio aplicado: {t.lower()} en un proyecto real"],
            })
        comp = p.get("competencias") or f"Diseña soluciones de {curso} aplicando {', '.join(temas[:3]).lower()}."
        return {
            "titulo": f"Sílabo — {curso}",
            "datos_generales": {"curso": curso, "carrera": carrera, "ciclo": str(p.get("ciclo") or "—"), "semanas": semanas, "creditos": 4, "modalidad": "Presencial"},
            "sumilla": f"{curso} es un curso de naturaleza teórico-práctica de la carrera de {carrera}. Aborda {', '.join(t.lower() for t in temas)}, articulando la teoría con proyectos aplicados para que el estudiante logre la siguiente competencia: {comp.rstrip('.')}.",
            "competencias": [_cap(c.strip()) for c in re.split(r"[;\n]", comp) if c.strip()] + ["Trabaja en equipo y comunica sus resultados con claridad."],
            "unidades": unidades,
            "metodologia": "Se emplea aprendizaje activo: exposiciones dialogadas, resolución de problemas en clase, laboratorios guiados y un proyecto final desarrollado por equipos con retroalimentación semanal.",
            "evaluacion": [
                {"instrumento": "Evaluación continua (laboratorios)", "semana": "2-15", "peso": 30},
                {"instrumento": "Examen parcial", "semana": str(max(1, semanas // 2)), "peso": 25},
                {"instrumento": "Proyecto final", "semana": str(max(1, semanas - 1)), "peso": 25},
                {"instrumento": "Examen final", "semana": str(semanas), "peso": 20},
            ],
            "bibliografia": [
                f"Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). Introduction to algorithms (4.ª ed.). MIT Press.",
                f"Sommerville, I. ({anio - 3}). Ingeniería de software (11.ª ed.). Pearson.",
                f"Autor institucional. ({anio - 1}). Guía de {curso.lower()}. Fondo Editorial Universitario.",
            ],
        }

    if tipo == "rubrica":
        criterios = p.get("criterios") or [(t, None) for t in temas]
        niveles = p.get("niveles") or ["Excelente", "Bueno", "En proceso", "Inicial"]
        nota = 20
        pesos = [c[1] for c in criterios]
        if any(w is None for w in pesos):
            base = round(100 / len(criterios), 2)
            pesos = [base] * len(criterios)
            pesos[-1] = round(100 - base * (len(criterios) - 1), 2)
        puntajes = [round(nota - i * (nota / len(niveles)), 1) for i in range(len(niveles))]
        cualidades = ["de forma sobresaliente y autónoma", "correctamente, con detalles menores por mejorar", "de manera parcial y con apoyo", "aún de forma incipiente"]
        return {
            "titulo": f"Rúbrica — {curso}",
            "descripcion": f"Rúbrica analítica para evaluar el desempeño de los estudiantes en {curso}. Cada criterio tiene un peso y cuatro niveles de logro con descriptores observables.",
            "nota_maxima": nota,
            "niveles": [{"nombre": n, "puntaje": puntajes[i]} for i, n in enumerate(niveles)],
            "criterios": [
                {"nombre": _cap(c[0]), "peso": pesos[i], "descriptores": [f"Evidencia {c[0].lower()} {cualidades[min(j, 3)]}." for j in range(len(niveles))]}
                for i, c in enumerate(criterios)
            ],
        }

    if tipo == "examen":
        total = int(p.get("num_preguntas") or 10)
        n_om = max(1, round(total * 0.7))
        n_de = max(1, total - n_om)
        letras = "ABCD"
        om = []
        for i in range(n_om):
            t = temas[i % len(temas)]
            correcta = random.Random(i).randint(0, 3)
            opciones = [f"Una afirmación incompleta sobre {t.lower()}", f"Una confusión frecuente sobre {t.lower()}", f"Un caso que no corresponde a {t.lower()}", f"Un ejemplo ajeno al curso"]
            opciones[correcta] = f"La definición correcta de {t.lower()} aplicada a {curso}"
            om.append({"enunciado": f"¿Cuál de las siguientes opciones describe mejor {t.lower()}?", "opciones": opciones, "respuesta": letras[correcta], "puntaje": round(12 / n_om, 1)})
        de = [
            {"enunciado": f"Explica y ejemplifica {temas[i % len(temas)].lower()} en un problema de {curso}.", "puntaje": round(8 / n_de, 1),
             "respuesta_esperada": f"Define {temas[i % len(temas)].lower()}, presenta un ejemplo resuelto paso a paso y justifica las decisiones tomadas."}
            for i in range(n_de)
        ]
        return {
            "titulo": f"Examen — {curso}",
            "instrucciones": "Lee con atención cada pregunta. Tienes 90 minutos. No se permite el uso de dispositivos. Marca una sola alternativa en las preguntas de opción múltiple y desarrolla tus respuestas con orden y claridad.",
            "preguntas_opcion_multiple": om,
            "preguntas_desarrollo": de,
        }

    # caso de estudio
    sector = p.get("sector") or "Retail"
    cantidad = int(p.get("num_preguntas") or 4)
    cantidad = max(1, min(cantidad, 20))
    problema = ", ".join(temas[:3]).lower()
    preguntas_base = [
        "¿Cuáles son las causas principales del problema y cómo se relacionan entre sí?",
        f"¿Qué conceptos de {curso} permiten analizar la situación de la empresa?",
        "Propón dos alternativas de solución y compáralas según costo, plazo e impacto.",
        "¿Qué indicadores usarías para verificar que la solución elegida funciona?",
        "¿Qué riesgos presenta cada alternativa y cómo podrían mitigarse?",
        "¿Qué decisiones deberían tomarse primero y cuál sería su justificación?",
        "¿Cómo adaptarías la propuesta a las restricciones presupuestarias de la organización?",
        "¿Qué información adicional sería necesaria antes de ejecutar la solución?",
        "Diseña un plan de implementación con responsables, plazos e hitos.",
        "¿Qué implicaciones éticas o normativas debe considerar el equipo?",
        "Explica cómo comunicarías la decisión a clientes, colaboradores y directivos.",
        "¿Qué supuestos has utilizado y cómo podrían cambiar tus conclusiones?",
        "¿Qué métricas financieras permitirían evaluar el impacto de la propuesta?",
        "¿Cómo manejarías una resistencia organizacional durante la implementación?",
        "¿Qué escenario desfavorable podría afectar el proyecto y qué contingencia aplicarías?",
        "Compara el costo de no actuar con el costo de implementar tu propuesta.",
        "¿Qué aprendizaje organizacional debería quedar después del proyecto?",
        "¿Qué resultados esperas observar durante las primeras ocho semanas?",
        "¿Qué criterios determinan si la solución debe ampliarse o detenerse?",
        "Presenta una recomendación final y relaciona cada decisión con los datos del caso.",
    ]
    adjuntos = p.get("adjuntos") or []
    contexto_real = "\n\n".join(
        str(a.get("texto") or "").strip()
        for a in adjuntos
        if str(a.get("texto") or "").strip()
    )[:18000]
    if contexto_real:
        datos_clave = [
            linea.strip()[:500]
            for linea in contexto_real.splitlines()
            if re.search(r"(venta|pedido|reclamo|retraso|zona|penalidad|semana|día|kpi|%|S/)", linea, re.I)
        ][:12]
        empresa_nombre = "Organización documentada en la fuente adjunta"
        razon = re.search(r"(Distribuciones\s+(?:Andinas|[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+){0,3})(?:\s+S\.A\.?(?:C\.?)?)?)", contexto_real)
        if razon:
            empresa_nombre = razon.group(1).strip()
        for linea in contexto_real.splitlines():
            if empresa_nombre != "Organización documentada en la fuente adjunta":
                break
            coincidencia = re.search(r"(?:empresa|organización)\s*:?\s*([A-ZÁÉÍÓÚÑ][^.,]{3,100})", linea, re.I)
            if coincidencia:
                empresa_nombre = coincidencia.group(1).strip()
                break
            if re.search(r"(Distribuciones|Andinas|S\.A\.|S\.A\.C\.|Market)", linea):
                empresa_nombre = linea.strip().lstrip("-• ").split(".")[0][:120]
                break
        return {
            "titulo": f"Caso de estudio — {curso}",
            "empresa": {
                "nombre": empresa_nombre,
                "sector": sector,
                "descripcion": f"Organización analizada a partir de documentación real del sector {sector.lower()}.",
            },
            "narrativa": (
                f"{contexto_real[:9000].strip()}\n\n"
                "Fuente proporcionada por el docente: la solución debe respetar los nombres, cifras, restricciones "
                "y decisiones documentadas. No se sustituyen los hechos reales por datos ficticios."
            ),
            "problema": f"¿Qué decisión debe tomar la organización para resolver {problema}, utilizando como base la situación y los datos documentados?",
            "datos_clave": datos_clave or ["Fuente real adjunta disponible para contrastar hechos y cifras."],
            "preguntas_discusion": preguntas_base[:cantidad],
        }
    return {
        "titulo": f"Caso de estudio — {curso}",
        "empresa": {"nombre": "Andina Market S.A.C.", "sector": sector, "descripcion": f"Empresa peruana del sector {sector.lower()} con 12 años en el mercado, 340 colaboradores y presencia en Lima y tres regiones."},
        "narrativa": (
            f"En el último año, Andina Market enfrentó un entorno más competitivo. La gerencia general detectó señales de alerta relacionadas con {problema}.\n\n"
            f"La gerente de operaciones, Lucía Paredes, convocó a su equipo para analizar la situación con datos de los últimos cuatro trimestres. Las opiniones del equipo se dividieron entre invertir en tecnología o reorganizar los procesos actuales.\n\n"
            f"El directorio exige una propuesta en 60 días, con indicadores medibles y un presupuesto que no supere el 5 % de las ventas anuales."
        ),
        "problema": f"¿Qué decisión debe tomar Andina Market para resolver los problemas asociados a {problema}, considerando sus restricciones de tiempo y presupuesto?",
        "datos_clave": ["Ventas anuales: S/ 48 millones", "Caída de margen: 3,2 puntos porcentuales", "Rotación de personal: 21 %", "Satisfacción del cliente: 68/100"],
        "preguntas_discusion": preguntas_base[:cantidad],
    }


# ----------------------------------------------------------------------
def _oraciones(texto: str) -> list[str]:
    return [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto or "") if o.strip()]


def regenerar_bloque(texto: str, instruccion: str = "") -> str:
    oraciones = _oraciones(texto) or [texto.strip() or "Contenido actualizado."]
    aperturas = ["En términos prácticos, ", "De manera concreta, ", "Para el estudiante, esto significa que ", "Con un enfoque aplicado, "]
    random.shuffle(aperturas)
    primera = oraciones[0]
    nueva = aperturas[0] + primera[:1].lower() + primera[1:]
    resto = " ".join(oraciones[1:])
    return f"<p>{nueva}{(' ' + resto) if resto else ''}</p>"


def responder_asistente(ctx: dict) -> str:
    mensaje = (ctx.get("mensaje") or "").lower()
    secciones = ctx.get("secciones") or []
    adjuntos = ctx.get("adjuntos") or []
    contexto_real = "\n\n".join(
        str(a.get("texto") or "").strip()
        for a in adjuntos
        if str(a.get("texto") or "").strip()
    )[:18000]
    cambios = []

    if contexto_real and any(palabra in mensaje for palabra in ("amplía", "ampliar", "desarrolla", "desarrollar", "extiende", "extender", "expande", "expandir", "detalla", "detallar")):
        if not secciones:
            secciones = []
        destino = next((s for s in secciones if s.get("clave") == "narrativa" or "descripción" in s.get("titulo", "").lower()), None)
        fragmento = contexto_real[:12000].strip()
        html_ampliado = (
            f"<p><strong>Contexto ampliado a partir de la fuente adjunta:</strong></p>"
            f"<p>{escape(fragmento[:7000].replace(chr(10), '</p><p>'))}</p>"
        )
        if destino:
            cambios.append({"id": destino["id"], "titulo": destino["titulo"], "html": destino["html"] + html_ampliado})
        else:
            cambios.append({"id": "nuevo", "titulo": "Descripción ampliada del caso", "html": html_ampliado})
        return "Amplié el caso incorporando hechos, cifras y restricciones presentes en el documento adjunto." + "\n" + MARCADOR + json.dumps({"tipo": "fuente_real", "secciones": cambios}, ensure_ascii=False)

    if "bibliograf" in mensaje or "apa" in mensaje:
        anio = date.today().year
        tema = ctx.get("curso") or "el curso"
        refs = [
            f"García, M., & Torres, L. ({anio - 1}). Fundamentos aplicados de {tema.lower()}. Editorial Académica.",
            f"Ramírez, J. ({anio - 2}). Enseñanza basada en proyectos en {tema.lower()}. Revista de Educación Superior, 18(2), 45-61. https://doi.org/10.0000/demo",
            f"Chen, Y., & Rojas, P. ({anio - 3}). Avances recientes en {tema.lower()}. Springer.",
        ]
        destino = next((s for s in secciones if "bibliograf" in (s.get("titulo", "").lower())), None)
        html_refs = "".join(f"<li>{r} <em>(por verificar)</em></li>" for r in refs)
        if destino:
            cambios.append({"id": destino["id"], "titulo": destino["titulo"], "html": destino["html"] + f"<ul>{html_refs}</ul>"})
        else:
            cambios.append({"id": "nuevo", "titulo": "Bibliografía", "html": f"<ul>{html_refs}</ul>"})
        return "Encontré 3 referencias en formato APA de los últimos 3 años. Están marcadas como «por verificar»: revísalas antes de insertarlas." + "\n" + MARCADOR + json.dumps({"tipo": "bibliografia", "secciones": cambios}, ensure_ascii=False)

    if "breve" in mensaje or "resume" in mensaje or "corto" in mensaje:
        for s in secciones:
            if s.get("oculta"):
                continue
            html = s.get("html", "")
            nuevo = re.sub(r"<p>(.*?)</p>", lambda m: "<p>" + (_oraciones(re.sub("<[^>]+>", "", m.group(1)))[:1] or [""])[0] + "</p>", html, flags=re.S)
            if nuevo != html:
                cambios.append({"id": s["id"], "titulo": s["titulo"], "html": nuevo})
        return "Listo, resumí los párrafos conservando la idea principal de cada sección." + "\n" + MARCADOR + json.dumps({"secciones": cambios}, ensure_ascii=False)

    m = re.search(r"(\d+)\s+preguntas", mensaje)
    if m and "pregunt" in mensaje:
        n = min(20, int(m.group(1)))
        destino = next((s for s in secciones if s.get("clave") == "desarrollo" or "desarrollo" in s.get("titulo", "").lower()), None)
        extra = "".join(f"<p><strong>Pregunta adicional {i}.</strong> Analiza un caso aplicado del curso y justifica tu respuesta. (2 pts)</p>" for i in range(1, n + 1))
        if destino:
            cambios.append({"id": destino["id"], "titulo": destino["titulo"], "html": destino["html"] + extra})
        return f"Preparé {n} preguntas adicionales para tu examen." + "\n" + MARCADOR + json.dumps({"secciones": cambios}, ensure_ascii=False)

    if "secci" in mensaje and ("agrega" in mensaje or "añade" in mensaje or "falta" in mensaje):
        faltante = ctx.get("faltantes", ["Sección nueva"])
        for titulo in faltante or ["Sección nueva"]:
            cambios.append({"id": "nuevo", "titulo": titulo, "html": f"<p>Contenido propuesto para la sección {titulo.lower()}. Complétalo con la información específica de tu curso.</p>"})
        return "Agregué las secciones obligatorias que faltaban con un contenido inicial." + "\n" + MARCADOR + json.dumps({"secciones": cambios}, ensure_ascii=False)

    if "nombre" in mensaje and ("empresa" in mensaje or "personaje" in mensaje):
        for s in secciones:
            html = s.get("html", "").replace("Andina Market", "Grupo Pacífico").replace("Lucía Paredes", "Andrés Salazar")
            if html != s.get("html"):
                cambios.append({"id": s["id"], "titulo": s["titulo"], "html": html})
        return "Cambié el nombre de la empresa y de los personajes en todo el caso." + "\n" + MARCADOR + json.dumps({"secciones": cambios}, ensure_ascii=False)

    if "ingl" in mensaje:
        return ("En modo demostración no hay un modelo de traducción disponible. Configura GEMINI_API_KEY o CLAUDE_API_KEY "
                "en el backend para traducir el documento completo.")

    return ("Entendido. En modo demostración puedo hacer el texto más breve, agregar bibliografía APA, agregar preguntas, "
            "completar secciones faltantes o cambiar nombres del caso. Con una clave de Gemini o Claude atiendo cualquier indicación.")
