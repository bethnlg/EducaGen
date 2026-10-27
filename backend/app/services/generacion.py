"""Generación de recursos con IA transmitida por SSE (I-02).

Flujo (Figura 30): datos del docente → RAG → prompt → adaptador (Gemini/Claude)
→ validación contra el esquema (un reintento correctivo) → versión 1 + borrador.
"""
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from ..config import config
from ..database import SessionLocal
from ..models import (
    Borrador,
    Carrera,
    Curso,
    RecursoEducativo,
    TiempoElaboracion,
    TipoRecurso,
    ValidacionEstructura,
    VersionRecurso,
)
from .esquemas import TIPOS, json_a_secciones, validar_json, verificar_conformidad
from .html_util import limpiar_html
from .llm import SinProveedoresError, adaptador
from .llm.base import estimar_tokens
from .monitoreo import crear_alerta, registrar_consulta, sincronizar_alerta_conformidad
from .prompts import extraer_json, hay_material_especifico, prompt_generacion, recuperar_materiales

log = logging.getLogger("educagen.generacion")


def sse(evento: dict) -> str:
    return f"data: {json.dumps(evento, ensure_ascii=False, default=str)}\n\n"


CABECERAS_SSE = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def _obtener_curso(db, nombre: str, carrera: str | None, ciclo: int | None) -> Curso:
    id_carrera = None
    if carrera:
        car = db.scalar(select(Carrera).where(func.lower(Carrera.nombre) == carrera.strip().lower()))
        if not car:
            car = Carrera(nombre=carrera.strip()[:120])
            db.add(car)
            db.flush()
        id_carrera = car.id_carrera
    curso = db.scalar(select(Curso).where(func.lower(Curso.nombre) == nombre.strip().lower(), Curso.id_carrera.is_(id_carrera) if id_carrera is None else Curso.id_carrera == id_carrera))
    if not curso:
        curso = Curso(nombre=nombre.strip()[:150], id_carrera=id_carrera, ciclo=ciclo)
        db.add(curso)
        db.flush()
    return curso


def crear_recurso_pendiente(db, id_usuario: int, params: dict) -> RecursoEducativo:
    tipo = params["tipo"]
    curso = _obtener_curso(db, params["curso"], params.get("carrera"), params.get("ciclo"))
    id_tipo = db.scalar(select(TipoRecurso.id_tipo_recurso).where(TipoRecurso.clave == tipo))
    recurso = RecursoEducativo(
        id_usuario=id_usuario, id_curso=curso.id_curso, id_tipo_recurso=id_tipo,
        titulo=f"{TIPOS[tipo]} — {params['curso']}"[:200], estado="generando",
    )
    db.add(recurso)
    db.flush()
    db.add(Borrador(id_recurso=recurso.id_recurso, contenido={"parametros": params, "secciones": []}))
    db.add(TiempoElaboracion(id_recurso=recurso.id_recurso))
    db.commit()
    return recurso


async def generar_stream(id_usuario: int, id_recurso: int, params: dict, avisos: list[str]):
    """Generador asíncrono de eventos SSE."""
    tipo = params["tipo"]
    db = SessionLocal()
    try:
        recurso = db.get(RecursoEducativo, id_recurso)
        recurso.estado = "generando"
        db.commit()
        yield sse({"tipo": "inicio", "id_recurso": id_recurso, "avisos": avisos})

        # RAG: materiales modelo del mismo tipo, carrera y ciclo (HU0010-1)
        consulta = f"{params['curso']} {' '.join(params.get('temas') or [])}"
        materiales = recuperar_materiales(db, tipo, params.get("carrera"), params.get("ciclo"), consulta)
        if not hay_material_especifico(materiales, params.get("carrera")):
            # HU0010-2: se usa la plantilla estándar si no hay materiales y se registra la falta
            crear_alerta(
                db, id_usuario=id_usuario, id_recurso=id_recurso, tipo="material_faltante", severidad="baja",
                titulo="Falta material modelo",
                descripcion=f"No hay un {TIPOS[tipo].lower()} modelo validado para {params.get('carrera') or 'la carrera indicada'}. Se aplicó el formato estándar de la universidad.",
            )
            db.commit()
        if materiales:
            yield sse({"tipo": "estado", "mensaje": f"Usando {len(materiales)} materiales modelo oficiales como referencia…"})
        else:
            materiales = []
            yield sse({"tipo": "estado", "mensaje": "Aplicando el formato estándar de la universidad…"})

        datos, faltantes, uso = None, [], None
        for intento in range(2):  # generación + un reintento correctivo (HU0034-2)
            sol = prompt_generacion(tipo, params, materiales, correctivo=faltantes if intento else None)
            texto = ""
            flujo = adaptador.stream(sol)
            try:
                async for ev in flujo:
                    if ev.tipo == "chunk":
                        texto += ev.texto
                        yield sse({"tipo": "chunk", "texto": ev.texto})
                        if estimar_tokens(texto) > config.MAX_TOKENS_SALIDA:  # HU0032-2
                            await flujo.aclose()
                            c = registrar_consulta(db, id_usuario=id_usuario, id_recurso=id_recurso, operacion="generacion",
                                                   uso=None, estado="detenida", materiales=materiales, tokens_salida=estimar_tokens(texto))
                            crear_alerta(db, id_usuario=id_usuario, id_recurso=id_recurso, id_consulta=c.id_consulta,
                                         tipo="consumo_inusual", severidad="alta", titulo="Consumo inusual de tokens",
                                         descripcion=f"La generación de «{recurso.titulo}» superó {config.MAX_TOKENS_SALIDA} tokens y fue detenida.", unica=False)
                            recurso.estado = "pendiente"
                            db.commit()
                            yield sse({"tipo": "error", "codigo": "consumo_inusual", "id_recurso": id_recurso,
                                       "mensaje": "La generación procesó mucho más texto de lo normal y se detuvo por seguridad. Revisa el Panel de calidad."})
                            return
                    elif ev.tipo == "reinicio":
                        texto = ""
                        yield sse({"tipo": "reinicio", "mensaje": "El servicio de IA tuvo una falla momentánea. Reintentando automáticamente…"})
                    elif ev.tipo == "fin":
                        uso = ev.uso
            except SinProveedoresError as e:  # HU0029-2
                log.error("Ningún proveedor respondió: %s", e)
                registrar_consulta(db, id_usuario=id_usuario, id_recurso=id_recurso, operacion="generacion",
                                   uso=None, estado="fallida", materiales=materiales)
                recurso.estado = "pendiente"
                db.commit()
                yield sse({"tipo": "error", "codigo": "ia_no_disponible", "id_recurso": id_recurso,
                           "mensaje": "Los servicios de IA no están disponibles en este momento. Guardamos tus datos como borrador: puedes reintentar más tarde desde el Historial."})
                return

            registrar_consulta(db, id_usuario=id_usuario, id_recurso=id_recurso, operacion="generacion",
                               uso=uso, estado="exitosa", materiales=materiales)
            db.commit()
            if uso and uso.conmutada:
                yield sse({"tipo": "estado", "mensaje": f"Generado con el servicio de respaldo ({uso.proveedor})."})

            datos = extraer_json(texto)
            faltantes = validar_json(tipo, datos)
            if not faltantes:
                break
            if intento == 0:
                yield sse({"tipo": "reinicio", "mensaje": "El recurso llegó incompleto. Regenerándolo automáticamente…"})

        if not isinstance(datos, dict):
            recurso.estado = "pendiente"
            db.commit()
            yield sse({"tipo": "error", "codigo": "respuesta_invalida", "id_recurso": id_recurso,
                       "mensaje": "La IA no devolvió un documento válido después de dos intentos. Tus datos quedaron guardados; vuelve a intentarlo."})
            return

        secciones = json_a_secciones(tipo, datos)
        for s in secciones:
            s["html"] = limpiar_html(s["html"])
        if faltantes:
            avisos.append("La IA no completó: " + ", ".join(faltantes) + ". Puedes pedírselo al asistente.")
        contenido = {"secciones": secciones, "parametros": params}

        recurso.titulo = (str(datos.get("titulo") or recurso.titulo)).strip()[:200]
        recurso.estado = "borrador"
        recurso.fecha_actualizacion = datetime.now(timezone.utc)
        version = VersionRecurso(id_recurso=id_recurso, numero_version=1, contenido=contenido, origen="ia")
        existente = db.scalar(select(VersionRecurso).where(VersionRecurso.id_recurso == id_recurso, VersionRecurso.numero_version == 1))
        if existente:
            existente.contenido, version = contenido, existente
        else:
            db.add(version)
        db.flush()
        conf = verificar_conformidad(tipo, secciones)
        db.add(ValidacionEstructura(id_version=version.id_version, conforme=conf["conforme"], secciones_faltantes=conf["faltantes"]))
        recurso.borrador.contenido = contenido
        recurso.borrador.fecha_guardado = datetime.now(timezone.utc)
        sincronizar_alerta_conformidad(db, recurso, conf)
        db.commit()
        yield sse({
            "tipo": "fin", "id_recurso": id_recurso, "titulo": recurso.titulo, "avisos": avisos,
            "proveedor": uso.proveedor if uso else None, "conmutada": bool(uso and uso.conmutada),
        })
    except Exception as e:  # pragma: no cover - errores inesperados
        log.exception("Error en la generación")
        db.rollback()
        try:
            r = db.get(RecursoEducativo, id_recurso)
            if r and r.estado == "generando":
                r.estado = "pendiente"
                db.commit()
        except Exception:
            pass
        yield sse({"tipo": "error", "codigo": "interno", "id_recurso": id_recurso, "mensaje": f"Ocurrió un error inesperado al generar el recurso ({type(e).__name__})."})
    finally:
        db.close()
