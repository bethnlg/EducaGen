"""Datos iniciales (idempotente): roles, tipos de recurso, carreras, banco de
materiales modelo (RAG) y migración de los usuarios del prototipo (data/usuarios.json).

Uso manual:  python -m app.seed
"""
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import BASE_DIR
from .database import Base, SessionLocal, engine
from .models import Carrera, MaterialModelo, Rol, TipoRecurso, Usuario
from .services.esquemas import ESQUEMAS_JSON, SECCIONES_OBLIGATORIAS, TIPOS

log = logging.getLogger("educagen.seed")

CARRERAS = [
    "Ingeniería de Software",
    "Ingeniería de Sistemas de Información",
    "Ciencias de la Computación",
    "Administración y Marketing",
    "Comunicación y Periodismo",
]

MATERIALES = [
    ("silabo", "Ingeniería de Software", 4, "Sílabo oficial — Estructuras de Datos", """
I. DATOS GENERALES: Curso: Estructuras de Datos. Carrera: Ingeniería de Software. Ciclo: 4. Créditos: 4. Semanas: 16. Modalidad: presencial.
II. SUMILLA: Curso teórico-práctico que desarrolla la capacidad de seleccionar, implementar y analizar estructuras de datos lineales y no lineales para resolver problemas computacionales con eficiencia.
III. COMPETENCIAS: Diseña soluciones algorítmicas eficientes (competencia general ABET 1). Analiza la complejidad temporal y espacial de sus soluciones. Trabaja en equipo en proyectos de software.
IV. UNIDADES DE APRENDIZAJE:
Unidad 1: Análisis de algoritmos (semanas 1-3). Logro: el estudiante estima la complejidad de algoritmos iterativos y recursivos. Contenidos: notación Big-O, mejor/peor caso, recurrencias.
Unidad 2: Estructuras lineales (semanas 4-7). Logro: implementa listas, pilas y colas. Contenidos: listas enlazadas, pilas, colas, aplicaciones.
Unidad 3: Árboles (semanas 8-12). Logro: implementa árboles binarios de búsqueda y balanceados. Contenidos: ABB, AVL, recorridos, heaps.
Unidad 4: Grafos (semanas 13-16). Logro: modela problemas con grafos. Contenidos: representación, BFS, DFS, Dijkstra.
V. METODOLOGÍA: aprendizaje activo, laboratorios semanales, proyecto por equipos con entregables quincenales.
VI. EVALUACIÓN: Laboratorios (semanas 2-15) 30 %; Examen parcial (semana 8) 25 %; Proyecto final (semana 15) 25 %; Examen final (semana 16) 20 %.
VII. BIBLIOGRAFÍA (APA 7): Cormen, T. H., et al. (2022). Introduction to algorithms (4.ª ed.). MIT Press. Weiss, M. A. (2020). Data structures and algorithm analysis in Java (4.ª ed.). Pearson.
"""),
    ("silabo", "Ingeniería de Software", 5, "Sílabo oficial — Bases de Datos", """
I. DATOS GENERALES: Curso: Bases de Datos. Carrera: Ingeniería de Software. Ciclo: 5. Créditos: 4. Semanas: 16.
II. SUMILLA: El curso desarrolla el diseño, implementación y consulta de bases de datos relacionales, desde el modelado conceptual hasta la optimización de consultas y el control de transacciones.
III. COMPETENCIAS: Modela datos de un dominio real. Implementa esquemas relacionales normalizados. Escribe consultas SQL eficientes.
IV. UNIDADES DE APRENDIZAJE: Unidad 1: Modelado conceptual (1-4). Unidad 2: Modelo relacional y normalización (5-8). Unidad 3: SQL avanzado (9-12). Unidad 4: Transacciones e índices (13-16). Cada unidad declara logro, semanas y contenidos.
V. METODOLOGÍA: clases invertidas, laboratorios en PostgreSQL, proyecto integrador.
VI. EVALUACIÓN: Prácticas calificadas 30 %, Parcial 25 %, Proyecto 25 %, Final 20 %.
VII. BIBLIOGRAFÍA (APA 7): Elmasri, R., & Navathe, S. (2021). Fundamentos de sistemas de bases de datos (7.ª ed.). Pearson.
"""),
    ("silabo", "Administración y Marketing", 3, "Sílabo oficial — Marketing Estratégico", """
I. DATOS GENERALES: Curso: Marketing Estratégico. Carrera: Administración y Marketing. Ciclo: 3. Créditos: 3. Semanas: 16.
II. SUMILLA: Curso teórico-práctico que desarrolla la capacidad de formular estrategias de marketing a partir del análisis del entorno y del consumidor.
III. COMPETENCIAS: Analiza el mercado y la competencia. Formula estrategias de segmentación y posicionamiento. Comunica propuestas con sustento en datos.
IV. UNIDADES DE APRENDIZAJE: Unidad 1: Análisis del entorno (1-4). Unidad 2: Comportamiento del consumidor (5-8). Unidad 3: Segmentación y posicionamiento (9-12). Unidad 4: Plan de marketing (13-16).
V. METODOLOGÍA: estudio de casos peruanos, trabajo de campo, exposiciones.
VI. EVALUACIÓN: Casos 30 %, Parcial 20 %, Plan de marketing 30 %, Final 20 %.
VII. BIBLIOGRAFÍA (APA 7): Kotler, P., & Keller, K. (2022). Marketing management (16.ª ed.). Pearson.
"""),
    ("rubrica", "Comunicación y Periodismo", 2, "Rúbrica oficial — Ensayo argumentativo", """
DESCRIPCIÓN: rúbrica analítica para evaluar ensayos argumentativos. Nota máxima: 20 puntos.
NIVELES DE DESEMPEÑO: Excelente (5), Bueno (4), En proceso (3), Inicial (1).
MATRIZ: Criterio 1. Tesis y argumentación (40 %): Excelente: plantea una tesis clara sostenida por tres argumentos sólidos; Bueno: tesis clara con argumentos suficientes; En proceso: tesis difusa; Inicial: no presenta tesis.
Criterio 2. Uso de fuentes (30 %): Excelente: integra al menos cuatro fuentes académicas citadas en APA 7; Bueno: tres fuentes con errores menores; En proceso: fuentes no académicas; Inicial: sin fuentes.
Criterio 3. Redacción (30 %): Excelente: texto cohesionado sin errores; Bueno: errores mínimos; En proceso: errores que dificultan la lectura; Inicial: texto desorganizado.
PUNTAJE TOTAL: suma ponderada de criterios convertida a escala vigesimal.
"""),
    ("rubrica", "Ingeniería de Software", 6, "Rúbrica oficial — Proyecto de software", """
DESCRIPCIÓN: rúbrica para evaluar el proyecto final de software por equipos. Nota máxima: 20.
NIVELES: Destacado (20), Logrado (15), En proceso (10), Inicial (5).
MATRIZ: Requisitos y alcance (20 %); Arquitectura y diseño (25 %); Calidad del código y pruebas (25 %); Documentación (15 %); Presentación y trabajo en equipo (15 %). Cada criterio describe un comportamiento observable por nivel.
PUNTAJE TOTAL: nota = Σ (puntaje del nivel × peso del criterio).
"""),
    ("examen", "Ingeniería de Software", 5, "Examen oficial — Parcial de Bases de Datos", """
INSTRUCCIONES: duración 90 minutos. Sin apuntes. Marque una alternativa por pregunta. Las preguntas de desarrollo se responden en el cuadernillo.
PREGUNTAS DE OPCIÓN MÚLTIPLE (12 puntos): 1. ¿Qué forma normal elimina las dependencias transitivas? A) 1FN B) 2FN C) 3FN D) FNBC. (1 pt) ... cada pregunta tiene cuatro alternativas y una sola correcta.
PREGUNTAS DE DESARROLLO (8 puntos): 9. Normalice hasta 3FN la relación propuesta y justifique cada paso. (4 pts) 10. Escriba una consulta SQL que obtenga los cinco clientes con mayor facturación del último trimestre. (4 pts)
CLAVE DE RESPUESTAS: 1-C ... 9: descomposición en tres relaciones sin dependencias transitivas. 10: SELECT con JOIN, GROUP BY, ORDER BY y LIMIT.
"""),
    ("caso", "Administración y Marketing", 5, "Caso oficial — Retail omnicanal", """
CONTEXTO DE LA EMPRESA: Tiendas Sol, cadena peruana de retail con 45 tiendas y canal online desde 2021.
DESCRIPCIÓN DEL CASO: la gerente comercial, Carla Mendoza, enfrenta una caída de 8 % en ventas presenciales mientras el canal digital crece 35 %, pero con altos costos logísticos. El directorio debe decidir si cerrar tiendas o convertirlas en centros de despacho.
DATOS CLAVE: ventas anuales S/ 320 millones; costo logístico online 14 % de la venta; NPS 41.
PROBLEMA A ANALIZAR: ¿qué estrategia omnicanal maximiza la rentabilidad en los próximos dos años?
PREGUNTAS DE DISCUSIÓN: 1. ¿Cuáles son las causas de la caída del canal presencial? 2. ¿Qué indicadores deberían guiar la decisión? 3. Compare dos alternativas estratégicas. 4. ¿Qué riesgos implica la alternativa recomendada?
"""),
    ("caso", "Ingeniería de Sistemas de Información", 7, "Caso oficial — Transformación digital en banca", """
CONTEXTO DE LA EMPRESA: Caja Andina, entidad microfinanciera con 600 000 clientes en zonas urbanas y rurales.
DESCRIPCIÓN DEL CASO: el gerente de TI, Jorge Quispe, debe migrar el core bancario a la nube en 18 meses sin interrumpir la atención. El equipo está dividido entre una migración progresiva y un reemplazo total.
DATOS CLAVE: 120 sistemas satélite; disponibilidad actual 98,7 %; presupuesto USD 4 millones.
PROBLEMA A ANALIZAR: ¿qué estrategia de migración reduce el riesgo operativo y regulatorio?
PREGUNTAS DE DISCUSIÓN: 1. Identifique los riesgos principales. 2. Evalúe ambas alternativas con criterios técnicos y de negocio. 3. Proponga una hoja de ruta. 4. ¿Cómo mediría el éxito de la migración?
"""),
]


def sembrar(db: Session):
    if not db.scalar(select(Rol).where(Rol.nombre == "docente")):
        db.add(Rol(id_rol=1, nombre="docente", descripcion="Docente universitario"))

    for clave, nombre in TIPOS.items():
        tipo = db.scalar(select(TipoRecurso).where(TipoRecurso.clave == clave))
        estructura = {"json": ESQUEMAS_JSON[clave], "secciones_obligatorias": [t for _, t, _ in SECCIONES_OBLIGATORIAS[clave]]}
        if not tipo:
            db.add(TipoRecurso(clave=clave, nombre=nombre, esquema_estructura=estructura))
        else:
            tipo.esquema_estructura = estructura

    for nombre in CARRERAS:
        if not db.scalar(select(Carrera).where(Carrera.nombre == nombre)):
            db.add(Carrera(nombre=nombre))
    db.flush()

    if not db.scalar(select(MaterialModelo.id_material).limit(1)):
        for tipo, carrera, ciclo, titulo, texto in MATERIALES:
            db.add(MaterialModelo(
                id_tipo_recurso=db.scalar(select(TipoRecurso.id_tipo_recurso).where(TipoRecurso.clave == tipo)),
                id_carrera=db.scalar(select(Carrera.id_carrera).where(Carrera.nombre == carrera)),
                ciclo=ciclo, titulo=titulo, contenido_texto=texto.strip(), estado="validado",
            ))

    # Migra los usuarios creados con el prototipo anterior (contraseñas bcrypt compatibles)
    archivo = BASE_DIR.parent / "data" / "usuarios.json"
    if archivo.is_file():
        try:
            for u in json.loads(archivo.read_text(encoding="utf-8")):
                correo = (u.get("correo") or "").strip().lower()
                if correo and u.get("password_hash") and not db.scalar(select(Usuario).where(Usuario.correo_institucional == correo)):
                    partes = (u.get("nombre") or correo).split(" ", 1)
                    db.add(Usuario(id_rol=1, nombres=partes[0], apellidos=partes[1] if len(partes) > 1 else "",
                                   correo_institucional=correo, hash_contrasena=u["password_hash"]))
        except (ValueError, OSError) as e:
            log.warning("No se pudieron migrar los usuarios de %s: %s", archivo, e)
    db.commit()


def inicializar():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        sembrar(db)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    inicializar()
    print("Base de datos inicializada.")
