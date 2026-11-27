"""Gestión de recursos educativos (EPICA0002 a EPICA0006)."""
import re
import uuid
from io import BytesIO
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import config
from ..database import get_db
from ..deps import obtener_recurso_propio, usuario_actual
from ..models import (
    Alerta,
    ArchivoAdjunto,
    ArchivoExportado,
    Borrador,
    ConsultaLLM,
    ConsultaMaterial,
    Curso,
    MaterialModelo,
    RecursoEducativo,
    RegistroEdicion,
    TiempoElaboracion,
    TipoRecurso,
    Usuario,
    ValidacionEstructura,
    VersionRecurso,
)
from ..schemas import BorradorIn, GenerarIn, RegenerarIn
from ..services.esquemas import TIPOS, normalizar, verificar_conformidad
from ..services.exportador import FORMATOS, ErrorExportacion, exportar
from ..services.universidades import UNIVERSIDADES_PRIVADAS_LIMA
from ..services.generacion import CABECERAS_SSE, crear_recurso_pendiente, generar_stream
from ..services.html_util import html_a_texto, limpiar_html
from ..services.llm import SinProveedoresError, adaptador
from ..services.metricas import porcentaje_modificado
from ..services.monitoreo import registrar_consulta, sincronizar_alerta_conformidad
from ..services.prompts import prompt_regeneracion

router = APIRouter(prefix="/api/recursos", tags=["recursos"])

SECTORES = ["Retail", "Banca y finanzas", "Salud", "Tecnología", "Educación", "Manufactura", "Minería", "Turismo", "Telecomunicaciones", "Sector público"]
NIVELES_DEFECTO = ["Excelente", "Bueno", "En proceso", "Inicial"]


def _extraer_texto_archivo(nombre: str, contenido: bytes) -> str:
    extension = Path(nombre).suffix.lower()
    if extension in {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm", ".py", ".js", ".ts", ".css", ".sql"}:
        return contenido.decode("utf-8", errors="replace")
    if extension == ".docx":
        from docx import Document
        documento = Document(BytesIO(contenido))
        partes = [p.text for p in documento.paragraphs if p.text.strip()]
        for tabla in documento.tables:
            for fila in tabla.rows:
                partes.append(" | ".join(celda.text.strip() for celda in fila.cells))
        return "\n".join(partes)
    if extension in {".xlsx", ".xlsm"}:
        from openpyxl import load_workbook
        libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True)
        return "\n".join(" | ".join("" if v is None else str(v) for v in fila) for hoja in libro.worksheets for fila in hoja.iter_rows(values_only=True))
    if extension == ".pptx":
        from pptx import Presentation
        presentacion = Presentation(BytesIO(contenido))
        partes = []
        for diapositiva in presentacion.slides:
            for forma in diapositiva.shapes:
                if getattr(forma, "has_text_frame", False):
                    partes.append(forma.text)
                if getattr(forma, "has_table", False):
                    for fila in forma.table.rows:
                        partes.append(" | ".join(celda.text.strip() for celda in fila.cells))
        return "\n".join(partes)
    if extension == ".pdf":
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(contenido)).pages)
    return ""


def _err(estado: int, mensaje: str, **extra):
    raise HTTPException(estado, detail={"mensaje": mensaje, **extra})


def _ahora():
    return datetime.now(timezone.utc)


def _aware(f):
    return f if f is None or f.tzinfo else f.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Validación de la solicitud de generación (HU0005-2, HU0006-2, HU0007-2, HU0008-2, HU0009-2)
# ---------------------------------------------------------------------------
def _lista(texto: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,;\n]", texto or "") if t.strip()]


def _parsear_criterios(texto: str) -> list[tuple[str, float | None]]:
    criterios = []
    for parte in _lista(texto):
        m = re.match(r"^(.*?)[\s:=(-]+(\d+(?:[.,]\d+)?)\s*%?\)?$", parte)
        if m and m.group(1).strip():
            criterios.append((m.group(1).strip(), float(m.group(2).replace(",", "."))))
        else:
            criterios.append((parte, None))
    return criterios


def _proponer_pesos(criterios, suma):
    """Redistribuye los pesos para que sumen 100 conservando la proporción."""
    if suma <= 0:
        base = round(100 / len(criterios), 2)
        pesos = [base] * len(criterios)
    else:
        pesos = [round((c[1] or 0) * 100 / suma, 1) for c in criterios]
    pesos[-1] = round(100 - sum(pesos[:-1]), 1)
    return [{"nombre": c[0], "peso": p} for c, p in zip(criterios, pesos)]


def validar_parametros(datos: GenerarIn) -> tuple[dict, list[str]]:
    tipo = datos.tipo if datos.tipo in TIPOS else None
    faltan = [c for c, v in (("tipo", tipo), ("curso", datos.curso.strip()), ("temas", datos.temas.strip())) if not v]
    if faltan:
        _err(422, "Completa los datos obligatorios para generar el recurso.", codigo="datos_incompletos", campos=faltan)

    avisos: list[str] = []
    params = {"tipo": tipo, "curso": datos.curso.strip(), "temas": _lista(datos.temas),
              "carrera": (datos.carrera or "").strip() or None, "ciclo": datos.ciclo}
    params["adjuntos"] = [a.model_dump() for a in datos.adjuntos]

    if tipo == "silabo":
        texto = datos.temas.strip()
        if (len(texto) < 25 or len(texto.split()) < 4) and not datos.forzar:
            _err(422, "Las competencias son muy breves. Descríbelas con más detalle (por ejemplo: «Diseña algoritmos eficientes usando recursividad y árboles») para obtener un sílabo más preciso.",
                 codigo="competencias_breves", campos=["temas"])
        params["competencias"] = texto
        params["semanas"] = datos.semanas or 16

    elif tipo == "rubrica":
        criterios = _parsear_criterios(datos.temas)
        niveles = _lista(datos.niveles or "") or NIVELES_DEFECTO
        if len(niveles) < 2:
            _err(422, "Indica al menos dos niveles de desempeño.", codigo="niveles", campos=["niveles"])
        con_peso = [c for c in criterios if c[1] is not None]
        if con_peso:
            if len(con_peso) != len(criterios):
                _err(422, "Asigna un peso a todos los criterios o a ninguno (ejemplo: «Redacción 30, Análisis 40, Fuentes 30»).", codigo="pesos_incompletos", campos=["temas"])
            suma = sum(c[1] for c in criterios)
            if abs(suma - 20) < 0.01:  # pesos expresados sobre la nota máxima de 20 puntos
                criterios = [(c[0], c[1] * 5) for c in criterios]
                suma = 100
            if abs(suma - 100) > 0.5:  # HU0007-2
                propuesta = _proponer_pesos(criterios, suma)
                if not datos.aceptar_propuesta:
                    _err(409, f"Los pesos suman {suma:g} % y deben sumar 100 % (nota máxima de 20 puntos). Te proponemos una nueva distribución.",
                         codigo="pesos_no_suman", suma=suma, propuesta=propuesta)
                criterios = [(p["nombre"], p["peso"]) for p in propuesta]
        params["criterios"] = criterios
        params["niveles"] = niveles

    elif tipo == "examen":
        n = datos.num_preguntas or 10
        if n > config.MAX_PREGUNTAS:  # HU0008-2
            avisos.append(f"Se generaron {config.MAX_PREGUNTAS} preguntas, el máximo por solicitud para cuidar la calidad. Pide al asistente «Agrega 10 preguntas» para un grupo adicional.")
            n = config.MAX_PREGUNTAS
        params["num_preguntas"] = n

    elif tipo == "caso":
        sector = (datos.sector or "").strip() or "Retail"
        if normalizar(sector) not in {normalizar(s) for s in SECTORES}:  # HU0009-2
            avisos.append(f"El sector «{sector}» no está en la lista: se usó una plantilla general adaptada. Puedes pedir al asistente que cambie los nombres de la empresa y los personajes.")
        params["sector"] = sector
        params["num_preguntas"] = min(datos.num_preguntas or 4, 20)
    return params, avisos


def _verificar_limite(db: Session, usuario: Usuario):
    total = db.scalar(select(func.count(RecursoEducativo.id_recurso)).where(
        RecursoEducativo.id_usuario == usuario.id_usuario, RecursoEducativo.fecha_eliminacion.is_(None)))
    if total >= config.MAX_RECURSOS:  # HU0018-2
        _err(409, f"Alcanzaste el máximo de {config.MAX_RECURSOS} recursos. Elimina recursos antiguos antes de crear uno nuevo.", codigo="limite_recursos")


@router.post("/generar")
def generar(datos: GenerarIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    params, avisos = validar_parametros(datos)
    _verificar_limite(db, usuario)
    recurso = crear_recurso_pendiente(db, usuario.id_usuario, params)
    return StreamingResponse(generar_stream(usuario.id_usuario, recurso.id_recurso, params, avisos),
                             media_type="text/event-stream", headers=CABECERAS_SSE)


@router.post("/archivos")
async def cargar_archivo(
    archivo: UploadFile = File(...),
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    """Carga un archivo de contexto y devuelve su texto extraíble para el prompt."""
    if not archivo.filename:
        _err(422, "Selecciona un archivo.")
    contenido = await archivo.read(config.MAX_ARCHIVO_ADJUNTO_BYTES + 1)
    if len(contenido) > config.MAX_ARCHIVO_ADJUNTO_BYTES:
        _err(413, f"El archivo supera el límite de {config.MAX_ARCHIVO_ADJUNTO_BYTES // (1024 * 1024)} MB.")
    usado = db.scalar(select(func.coalesce(func.sum(ArchivoAdjunto.tamano), 0)).where(
        ArchivoAdjunto.id_usuario == usuario.id_usuario)) or 0
    if usado + len(contenido) > config.MAX_ALMACEN_ADJUNTOS_USUARIO:
        _err(413, "Alcanzaste tu cuota de almacenamiento de archivos de referencia (50 MB). Elimina archivos antiguos para continuar.")
    try:
        texto = _extraer_texto_archivo(archivo.filename, contenido)
    except (ImportError, KeyError, OSError, TypeError, ValueError) as exc:
        raise HTTPException(422, detail={"mensaje": "No se pudo leer el archivo. Puedes adjuntarlo, pero la IA no usará su contenido.", "codigo": "archivo_no_legible"}) from exc
    carpeta = config.STORAGE_DIR / "uploads" / str(usuario.id_usuario)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{uuid.uuid4().hex}{Path(archivo.filename).suffix.lower()[:10]}"
    ruta.write_bytes(contenido)
    adjunto = ArchivoAdjunto(
        id_archivo=ruta.stem, id_usuario=usuario.id_usuario, nombre=archivo.filename[:200],
        tipo=(archivo.content_type or "application/octet-stream")[:150], tamano=len(contenido),
        ruta=str(ruta), texto=texto[:config.MAX_TEXTO_ADJUNTO], texto_extraido=bool(texto.strip()),
    )
    db.add(adjunto)
    db.commit()
    return {
        "id": adjunto.id_archivo,
        "nombre": archivo.filename[:200],
        "tipo": archivo.content_type or "application/octet-stream",
        "tamano": len(contenido),
        "texto": texto[:config.MAX_TEXTO_ADJUNTO],
        "texto_extraido": bool(texto.strip()),
    }


@router.delete("/archivos/{id_archivo}")
def eliminar_adjunto_pendiente(id_archivo: str, usuario: Usuario = Depends(usuario_actual),
                               db: Session = Depends(get_db)):
    """Elimina un archivo cargado por el usuario antes de asociarlo a un recurso."""
    adjunto = db.scalar(select(ArchivoAdjunto).where(
        ArchivoAdjunto.id_archivo == id_archivo,
        ArchivoAdjunto.id_usuario == usuario.id_usuario,
    ))
    if not adjunto:
        _err(404, "El archivo no existe.")
    try:
        Path(adjunto.ruta).unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(adjunto)
    db.commit()
    return {"ok": True}


@router.post("/{id_recurso}/generar")
def reintentar_generacion(id_recurso: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Reintenta un recurso que quedó pendiente porque la IA no estaba disponible (HU0029-2)."""
    recurso = obtener_recurso_propio(db, id_recurso, usuario)
    params = (recurso.borrador.contenido or {}).get("parametros") if recurso.borrador else None
    if not params:
        _err(400, "Este recurso no tiene datos de generación guardados.")
    return StreamingResponse(generar_stream(usuario.id_usuario, recurso.id_recurso, params, []),
                             media_type="text/event-stream", headers=CABECERAS_SSE)


# ---------------------------------------------------------------------------
# Historial (HU0017, HU0019, HU0018, HU0020)
# ---------------------------------------------------------------------------
def _resumen(r: RecursoEducativo) -> dict:
    secciones = (r.borrador.contenido or {}).get("secciones", []) if r.borrador else []
    conf = verificar_conformidad(r.tipo.clave, secciones) if secciones else None
    return {
        "id": r.id_recurso, "titulo": r.titulo, "tipo": r.tipo.clave, "tipo_nombre": r.tipo.nombre,
        "curso": r.curso.nombre if r.curso else "", "estado": r.estado,
        "conforme": conf["conforme"] if conf else None, "conformidad": conf["porcentaje"] if conf else None,
        "fecha_creacion": _aware(r.fecha_creacion), "fecha_actualizacion": _aware(r.fecha_actualizacion),
        "fecha_eliminacion": _aware(r.fecha_eliminacion),
    }


def _purgar_papelera(db: Session, usuario: Usuario):
    limite = _ahora() - timedelta(days=config.DIAS_PAPELERA)
    for r in db.scalars(select(RecursoEducativo).where(RecursoEducativo.id_usuario == usuario.id_usuario,
                                                       RecursoEducativo.fecha_eliminacion.is_not(None))):
        if _aware(r.fecha_eliminacion) < limite:
            db.delete(r)
    db.commit()


@router.get("")
def listar(q: str = Query(default="", max_length=120), tipo: str = Query(default=""), papelera: bool = False,
           limite: int = Query(default=200, ge=1, le=500), usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    _purgar_papelera(db, usuario)
    base = select(RecursoEducativo).join(Curso).join(TipoRecurso).where(RecursoEducativo.id_usuario == usuario.id_usuario)
    base = base.where(RecursoEducativo.fecha_eliminacion.is_not(None) if papelera else RecursoEducativo.fecha_eliminacion.is_(None))

    conteos = {clave: 0 for clave in TIPOS}
    for clave, n in db.execute(select(TipoRecurso.clave, func.count()).select_from(RecursoEducativo).join(TipoRecurso)
                               .where(RecursoEducativo.id_usuario == usuario.id_usuario, RecursoEducativo.fecha_eliminacion.is_(None))
                               .group_by(TipoRecurso.clave)):
        conteos[clave] = n

    consulta = base
    if tipo in TIPOS:
        consulta = consulta.where(TipoRecurso.clave == tipo)
    if q.strip():
        patron = f"%{q.strip()}%"
        consulta = consulta.where(or_(RecursoEducativo.titulo.ilike(patron), Curso.nombre.ilike(patron)))
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    recursos = db.scalars(consulta.order_by(RecursoEducativo.fecha_actualizacion.desc()).limit(limite)).all()
    return {"recursos": [_resumen(r) for r in recursos], "conteos": conteos, "total": total}


@router.get("/{id_recurso}")
def detalle(id_recurso: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    contenido = r.borrador.contenido if r.borrador else {"secciones": []}
    secciones = contenido.get("secciones", [])
    from ..models import MensajeAsistente  # import local para evitar ciclos

    mensajes = db.scalars(select(MensajeAsistente).where(MensajeAsistente.id_recurso == r.id_recurso)
                          .order_by(MensajeAsistente.fecha_envio)).all()
    ultima = db.scalar(select(func.max(VersionRecurso.numero_version)).where(VersionRecurso.id_recurso == r.id_recurso)) or 0
    return {
        **_resumen(r),
        "contenido": {"secciones": secciones},
        "parametros": contenido.get("parametros"),
        "conformidad_detalle": verificar_conformidad(r.tipo.clave, secciones),
        "fecha_guardado": _aware(r.borrador.fecha_guardado) if r.borrador else None,
        "fecha_aprobacion": _aware(r.fecha_aprobacion),
        "version_actual": ultima,
        "segundos_activos": r.tiempo.segundos_activos if r.tiempo else 0,
        "mensajes": [{"id": m.id_mensaje, "emisor": m.emisor, "contenido": m.contenido, "propuesta": m.propuesta,
                      "aplicado": m.aplicado, "fecha": _aware(m.fecha_envio)} for m in mensajes],
        "adjuntos": [{"id": a.id_archivo, "nombre": a.nombre, "tipo": a.tipo, "tamano": a.tamano,
                      "texto": a.texto, "texto_extraido": a.texto_extraido, "fecha": _aware(a.fecha_carga)}
                     for a in db.scalars(select(ArchivoAdjunto).where(ArchivoAdjunto.id_recurso == r.id_recurso)
                                         .order_by(ArchivoAdjunto.fecha_carga)).all()],
    }


@router.delete("/{id_recurso}/archivos/{id_archivo}")
def eliminar_adjunto(id_recurso: int, id_archivo: str, usuario: Usuario = Depends(usuario_actual),
                     db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    adjunto = db.scalar(select(ArchivoAdjunto).where(
        ArchivoAdjunto.id_archivo == id_archivo,
        ArchivoAdjunto.id_usuario == usuario.id_usuario,
        or_(ArchivoAdjunto.id_recurso == r.id_recurso, ArchivoAdjunto.id_recurso.is_(None)),
    ))
    if not adjunto:
        _err(404, "El archivo no existe o no pertenece a este recurso.")
    try:
        Path(adjunto.ruta).unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(adjunto)
    db.commit()
    return {"ok": True}


@router.get("/{id_recurso}/versiones")
def listar_versiones(id_recurso: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    versiones = db.scalars(select(VersionRecurso).where(VersionRecurso.id_recurso == r.id_recurso)
                           .order_by(VersionRecurso.numero_version.desc())).all()
    return {
        "versiones": [{
            "id": v.id_version,
            "numero": v.numero_version,
            "origen": v.origen,
            "fecha": _aware(v.fecha_creacion),
            "secciones": len((v.contenido or {}).get("secciones", [])),
        } for v in versiones],
    }


@router.post("/{id_recurso}/versiones/{id_version}/restaurar")
def restaurar_version(id_recurso: int, id_version: int, usuario: Usuario = Depends(usuario_actual),
                      db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    version = db.scalar(select(VersionRecurso).where(
        VersionRecurso.id_version == id_version, VersionRecurso.id_recurso == r.id_recurso))
    if not version:
        _err(404, "La versión no existe.")
    if r.estado == "generando":
        _err(409, "Espera a que termine la generación antes de restaurar una versión.")
    secciones = _limpiar_secciones((version.contenido or {}).get("secciones", []))
    guardar_contenido(db, r, secciones)
    db.commit()
    return {
        "ok": True,
        "contenido": {"secciones": secciones},
        "estado": r.estado,
        "fecha_guardado": _aware(r.borrador.fecha_guardado),
        "conformidad": verificar_conformidad(r.tipo.clave, secciones),
    }


# ---------------------------------------------------------------------------
# Edición y guardado automático (HU0015, HU0016, HU0027-2)
# ---------------------------------------------------------------------------
def _limpiar_secciones(secciones: list) -> list[dict]:
    limpias = []
    for s in secciones or []:
        if not isinstance(s, dict):
            continue
        limpias.append({
            "id": str(s.get("id") or "s" + uuid.uuid4().hex[:8])[:40],
            "clave": s.get("clave"),
            "titulo": str(s.get("titulo") or "")[:200],
            "html": limpiar_html(str(s.get("html") or "")),
            **({"oculta": True} if s.get("oculta") else {}),
        })
    return limpias


def guardar_contenido(db: Session, r: RecursoEducativo, secciones: list[dict]) -> dict:
    contenido = dict(r.borrador.contenido or {})
    contenido["secciones"] = secciones
    r.borrador.contenido = contenido
    r.borrador.fecha_guardado = _ahora()
    r.fecha_actualizacion = _ahora()
    if r.estado in ("aprobado", "pendiente", "generando"):
        r.estado = "borrador"  # HU0027-2: cualquier cambio posterior abre una nueva versión en borrador
    if r.tiempo:
        r.tiempo.numero_ediciones += 1
    conf = verificar_conformidad(r.tipo.clave, secciones)
    sincronizar_alerta_conformidad(db, r, conf)
    return conf


@router.put("/{id_recurso}/borrador")
@router.post("/{id_recurso}/borrador")  # POST permite navigator.sendBeacon al cerrar la pestaña
def guardar_borrador(id_recurso: int, datos: BorradorIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    if not r.borrador:
        db.add(Borrador(id_recurso=r.id_recurso, contenido={"secciones": []}))
        db.flush()
        db.refresh(r)
    if r.tiempo is None:
        db.add(TiempoElaboracion(id_recurso=r.id_recurso))
        db.flush()
        db.refresh(r)
    # El tiempo activo solo se mide hasta la aprobación (RF-09)
    if datos.segundos_activos and r.estado != "aprobado":
        r.tiempo.segundos_activos += datos.segundos_activos
    conf = None
    if datos.titulo and datos.titulo.strip():
        r.titulo = datos.titulo.strip()[:200]
        r.fecha_actualizacion = _ahora()
    if datos.contenido is not None:
        conf = guardar_contenido(db, r, _limpiar_secciones(datos.contenido.get("secciones", [])))
    db.commit()
    return {"ok": True, "estado": r.estado, "fecha_guardado": _aware(r.borrador.fecha_guardado),
            "conformidad": conf or verificar_conformidad(r.tipo.clave, (r.borrador.contenido or {}).get("secciones", []))}


@router.post("/{id_recurso}/regenerar")
async def regenerar(id_recurso: int, datos: RegenerarIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """HU0011: reescribe solo el fragmento seleccionado."""
    r = obtener_recurso_propio(db, id_recurso, usuario)
    if datos.intento > config.MAX_REGENERACIONES:  # HU0011-2
        _err(429, f"Alcanzaste el límite de {config.MAX_REGENERACIONES} nuevas redacciones seguidas para este fragmento. Te sugerimos editarlo a mano.", codigo="limite_regeneraciones")
    secciones = (r.borrador.contenido or {}).get("secciones", [])
    seccion = next((s for s in secciones if s.get("id") == datos.seccion_id), None)
    if not seccion:
        _err(404, "No se encontró la sección. Guarda el documento e inténtalo otra vez.")
    bloque = limpiar_html(datos.bloque_html)
    texto = html_a_texto(bloque)
    if not texto.strip():
        _err(422, "Selecciona un párrafo con texto para regenerarlo.")
    sol = prompt_regeneracion(r.tipo.clave, seccion.get("titulo", ""), html_a_texto(seccion.get("html", "")), bloque, texto, datos.instruccion)
    try:
        respuesta, uso = await adaptador.completar(sol)
    except SinProveedoresError:
        registrar_consulta(db, id_usuario=usuario.id_usuario, id_recurso=r.id_recurso, operacion="regeneracion", uso=None, estado="fallida")
        db.commit()
        _err(503, "Los servicios de IA no están disponibles. Inténtalo en unos minutos.")
    registrar_consulta(db, id_usuario=usuario.id_usuario, id_recurso=r.id_recurso, operacion="regeneracion", uso=uso, estado="exitosa")
    db.commit()
    nuevo = limpiar_html(re.sub(r"^```(?:html)?|```$", "", respuesta.strip()).strip())
    if not html_a_texto(nuevo).strip():
        _err(502, "La IA devolvió un fragmento vacío. Vuelve a intentarlo.")
    return {"html": nuevo, "intentos_restantes": config.MAX_REGENERACIONES - datos.intento}


@router.post("/{id_recurso}/duplicar", status_code=201)
def duplicar(id_recurso: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    _verificar_limite(db, usuario)
    copia = RecursoEducativo(id_usuario=usuario.id_usuario, id_curso=r.id_curso, id_tipo_recurso=r.id_tipo_recurso,
                             id_recurso_origen=r.id_recurso, titulo=f"{r.titulo} (Copia)"[:200], estado="borrador")
    db.add(copia)
    db.flush()
    contenido = dict(r.borrador.contenido) if r.borrador else {"secciones": []}
    db.add(Borrador(id_recurso=copia.id_recurso, contenido=contenido))
    # La copia toma el contenido actual como punto de partida para medir sus propias ediciones
    db.add(VersionRecurso(id_recurso=copia.id_recurso, numero_version=1, contenido=contenido, origen="ia"))
    db.add(TiempoElaboracion(id_recurso=copia.id_recurso))
    db.commit()
    return {"ok": True, "id": copia.id_recurso, "titulo": copia.titulo}


@router.delete("/{id_recurso}")
def eliminar(id_recurso: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    r.fecha_eliminacion = _ahora()  # HU0020-1: papelera temporal de 30 días
    for a in db.scalars(select(Alerta).where(Alerta.id_recurso == r.id_recurso, Alerta.atendida.is_(False))):
        a.atendida = True
    db.commit()
    return {"ok": True, "dias_papelera": config.DIAS_PAPELERA}


@router.post("/{id_recurso}/restaurar")
def restaurar(id_recurso: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario, incluir_eliminados=True)
    r.fecha_eliminacion = None
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Aprobación (HU0027, HU0025)
# ---------------------------------------------------------------------------
def _version_ia(db: Session, r: RecursoEducativo) -> VersionRecurso | None:
    return db.scalar(select(VersionRecurso).where(VersionRecurso.id_recurso == r.id_recurso, VersionRecurso.origen == "ia")
                     .order_by(VersionRecurso.numero_version.desc()))


def _datos_aprobacion(db: Session, r: RecursoEducativo) -> dict:
    secciones = (r.borrador.contenido or {}).get("secciones", [])
    conf = verificar_conformidad(r.tipo.clave, secciones)
    ia = _version_ia(db, r)
    pct = porcentaje_modificado(ia.contenido, {"secciones": secciones}) if ia else 0.0
    ultima = db.scalar(select(func.max(VersionRecurso.numero_version)).where(VersionRecurso.id_recurso == r.id_recurso)) or 0

    # Materiales modelo usados en la última generación (RAG)
    consulta = db.scalar(select(ConsultaLLM).where(ConsultaLLM.id_recurso == r.id_recurso, ConsultaLLM.tipo_operacion == "generacion",
                                                   ConsultaLLM.estado == "exitosa").order_by(ConsultaLLM.fecha_consulta.desc()))
    materiales = []
    if consulta:
        materiales = db.scalars(select(MaterialModelo).join(ConsultaMaterial, ConsultaMaterial.id_material == MaterialModelo.id_material)
                                .where(ConsultaMaterial.id_consulta == consulta.id_consulta)).all()
    alertas = db.scalar(select(func.count(Alerta.id_alerta)).where(Alerta.id_recurso == r.id_recurso, Alerta.atendida.is_(False),
                                                                   Alerta.tipo != "material_faltante")) or 0
    carreras = sorted({m.carrera.nombre for m in materiales if m.carrera})
    return {
        "conformidad": conf,
        "materiales": {
            "cantidad": len(materiales),
            "descripcion": (f"Validado contra {len(materiales)} {r.tipo.nombre.lower()}{'s' if len(materiales) != 1 else ''} oficial{'es' if len(materiales) != 1 else ''}"
                            + (f" de {', '.join(carreras)}" if carreras else "")) if materiales else "Se aplicó el formato estándar de la universidad",
        },
        "alertas_activas": alertas,
        "version_a_aprobar": ultima + 1,
        "minutos_activos": round((r.tiempo.segundos_activos if r.tiempo else 0) / 60),
        "porcentaje_editado": pct,
        "estado": r.estado,
    }


@router.get("/{id_recurso}/aprobacion")
def vista_aprobacion(id_recurso: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _datos_aprobacion(db, obtener_recurso_propio(db, id_recurso, usuario))


@router.post("/{id_recurso}/aprobar")
def aprobar(id_recurso: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    if r.estado == "aprobado":
        _err(409, "Este recurso ya está aprobado. Si lo editas se creará una nueva versión.")
    if r.estado in ("generando", "pendiente"):
        _err(409, "El recurso todavía no tiene contenido generado.")
    datos = _datos_aprobacion(db, r)
    secciones = (r.borrador.contenido or {}).get("secciones", [])
    final = VersionRecurso(id_recurso=r.id_recurso, numero_version=datos["version_a_aprobar"],
                           contenido={"secciones": secciones}, origen="docente")
    db.add(final)
    db.flush()
    conf = datos["conformidad"]
    db.add(ValidacionEstructura(id_version=final.id_version, conforme=conf["conforme"], secciones_faltantes=conf["faltantes"]))
    ia = _version_ia(db, r)
    if ia:
        db.add(RegistroEdicion(id_recurso=r.id_recurso, id_version_ia=ia.id_version, id_version_final=final.id_version,
                               porcentaje_modificado=datos["porcentaje_editado"]))
    ahora = _ahora()
    r.estado = "aprobado"
    r.fecha_aprobacion = ahora
    r.fecha_actualizacion = ahora
    if r.tiempo:
        r.tiempo.fecha_aprobacion = ahora
    db.commit()
    return {"ok": True, "estado": r.estado, "fecha_aprobacion": ahora, "version": final.numero_version,
            "porcentaje_editado": datos["porcentaje_editado"], "minutos_activos": datos["minutos_activos"]}


# ---------------------------------------------------------------------------
# Exportación (HU0021, HU0022, HU0023)
# ---------------------------------------------------------------------------
def _nombre_archivo(titulo: str, ext: str) -> str:
    base = normalizar(titulo)
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:80] or "recurso"
    return f"{base}.{ext}"


@router.get("/{id_recurso}/exportar")
def exportar_recurso(id_recurso: int, request: Request, formato: str = "pdf", membrete: bool = False, clave: bool = True,
                     universidad: str = "upc",
                     usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    formato = formato.lower()
    if formato not in FORMATOS:
        _err(400, "Formato no admitido. Elige PDF, Word, Excel, HTML o texto.")
    secciones = (r.borrador.contenido or {}).get("secciones", [])
    if not secciones:
        _err(409, "El recurso aún no tiene contenido para exportar.")
    universidad_info = UNIVERSIDADES_PRIVADAS_LIMA.get(universidad)
    if not universidad_info:
        _err(400, "La universidad seleccionada no está disponible.")
    try:
        datos, mime, ext = exportar(formato, r.titulo, secciones, membrete, incluir_ocultas=clave,
                                    meta={
                                        "curso": r.curso.nombre if r.curso else "",
                                        "docente": usuario.nombre_completo,
                                        "universidad_clave": universidad,
                                        "universidad_nombre": universidad_info["nombre"],
                                    })
    except ErrorExportacion as e:  # HU0021-2
        _err(500, f"{e}. Puedes descargarlo en otro formato.", codigo="error_conversion",
             alternativas=[f for f in FORMATOS if f != formato])

    # Almacenamiento del archivo y registro de metadatos (archivo_exportado)
    carpeta = config.STORAGE_DIR / str(usuario.id_usuario)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{uuid.uuid4().hex}.{ext}"
    ruta.write_bytes(datos)
    version = db.scalar(select(VersionRecurso.id_version).where(VersionRecurso.id_recurso == r.id_recurso)
                        .order_by(VersionRecurso.numero_version.desc()))
    db.add(ArchivoExportado(id_recurso=r.id_recurso, id_version=version, formato=formato, incluye_membrete=membrete,
                            ruta_s3=str(ruta), fecha_expiracion_enlace=_ahora() + timedelta(hours=config.HORAS_ENLACE_DESCARGA)))
    db.commit()
    nombre = _nombre_archivo(r.titulo, ext)
    return Response(content=datos, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="{nombre}"',
        "Cache-Control": "no-store",
    })
