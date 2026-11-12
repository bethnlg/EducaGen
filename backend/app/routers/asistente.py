"""Asistente inteligente del editor: respuestas en streaming y «Aplicar al texto»."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..deps import obtener_recurso_propio, usuario_actual
from ..models import ArchivoAdjunto, MensajeAsistente, Usuario
from ..schemas import AplicarIn, AsistenteIn
from ..services.esquemas import verificar_conformidad
from ..services.generacion import CABECERAS_SSE, sse
from ..services.html_util import limpiar_html
from ..services.llm import MARCADOR, SinProveedoresError, adaptador
from ..services.monitoreo import registrar_consulta
from ..services.prompts import extraer_json, prompt_asistente
from .recursos import _limpiar_secciones, guardar_contenido

router = APIRouter(prefix="/api/recursos", tags=["asistente"])

def _err(estado: int, mensaje: str, **extra):
    raise HTTPException(estado, detail={"mensaje": mensaje, **extra})


@router.post("/{id_recurso}/asistente")
def consultar(id_recurso: int, datos: AsistenteIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    mensaje = datos.mensaje.strip()
    if not mensaje:  # HU0012-2
        _err(422, "Escribe al menos una palabra para el asistente.")
    secciones = _limpiar_secciones(datos.secciones) if datos.secciones else (r.borrador.contenido or {}).get("secciones", [])
    ids_adjuntos = [a.id for a in datos.adjuntos]
    if ids_adjuntos:
        adjuntos = db.scalars(select(ArchivoAdjunto).where(
            ArchivoAdjunto.id_archivo.in_(ids_adjuntos),
            ArchivoAdjunto.id_usuario == usuario.id_usuario,
            ArchivoAdjunto.id_recurso.is_(None),
        )).all()
        for adjunto in adjuntos:
            adjunto.id_recurso = r.id_recurso
    historial = [(m.emisor, m.contenido) for m in db.scalars(
        select(MensajeAsistente).where(MensajeAsistente.id_recurso == r.id_recurso).order_by(MensajeAsistente.fecha_envio))]
    faltantes = verificar_conformidad(r.tipo.clave, secciones)["faltantes"]
    sol = prompt_asistente(r.tipo.clave, r.titulo, secciones, mensaje, historial, faltantes, r.curso.nombre if r.curso else "", [a.model_dump() for a in datos.adjuntos])
    db.add(MensajeAsistente(id_recurso=r.id_recurso, emisor="docente", contenido=mensaje))
    db.commit()
    return StreamingResponse(_stream(usuario.id_usuario, r.id_recurso, sol), media_type="text/event-stream", headers=CABECERAS_SSE)


async def _stream(id_usuario: int, id_recurso: int, sol):
    """Transmite solo la parte visible; el JSON de cambios después del marcador se procesa al final."""
    db = SessionLocal()
    try:
        total, enviado, uso = "", 0, None
        try:
            async for ev in adaptador.stream(sol):
                if ev.tipo == "chunk":
                    total += ev.texto
                    corte = total.find(MARCADOR)
                    visible = total[:corte] if corte >= 0 else total[: max(0, len(total) - len(MARCADOR))]
                    if len(visible) > enviado:
                        yield sse({"tipo": "chunk", "texto": visible[enviado:]})
                        enviado = len(visible)
                elif ev.tipo == "reinicio":
                    total, enviado = "", 0
                    yield sse({"tipo": "reinicio"})
                elif ev.tipo == "fin":
                    uso = ev.uso
        except SinProveedoresError:
            registrar_consulta(db, id_usuario=id_usuario, id_recurso=id_recurso, operacion="asistente", uso=None, estado="fallida")
            db.commit()
            yield sse({"tipo": "error", "mensaje": "El asistente no está disponible en este momento. Vuelve a intentarlo en unos minutos."})
            return

        corte = total.find(MARCADOR)
        visible = (total[:corte] if corte >= 0 else total).strip()
        if len(visible) > enviado:
            yield sse({"tipo": "chunk", "texto": visible[enviado:]})
        propuesta = None
        if corte >= 0:
            datos = extraer_json(total[corte + len(MARCADOR):])
            if isinstance(datos, dict) and isinstance(datos.get("secciones"), list):
                cambios = []
                for s in datos["secciones"]:
                    if isinstance(s, dict) and (s.get("html") or s.get("titulo")):
                        cambios.append({"id": str(s.get("id") or "nuevo"), "titulo": str(s.get("titulo") or "")[:200],
                                        "html": limpiar_html(str(s.get("html") or ""))})
                if cambios:
                    propuesta = {"tipo": datos.get("tipo") or "cambio", "secciones": cambios}
        registrar_consulta(db, id_usuario=id_usuario, id_recurso=id_recurso, operacion="asistente", uso=uso, estado="exitosa")
        m = MensajeAsistente(id_recurso=id_recurso, emisor="asistente", contenido=visible or "Listo.", propuesta=propuesta)
        db.add(m)
        db.commit()
        yield sse({"tipo": "fin", "id_mensaje": m.id_mensaje, "contenido": m.contenido, "propuesta": propuesta})
    finally:
        db.close()


@router.post("/{id_recurso}/asistente/{id_mensaje}/aplicar")
def aplicar(id_recurso: int, id_mensaje: int, datos: AplicarIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = obtener_recurso_propio(db, id_recurso, usuario)
    m = db.get(MensajeAsistente, id_mensaje)
    if not m or m.id_recurso != r.id_recurso or not m.propuesta:
        _err(404, "No hay cambios para aplicar en este mensaje.")
    if m.aplicado:
        _err(409, "Este cambio ya fue aplicado.")
    if m.propuesta.get("tipo") == "bibliografia" and not datos.confirmado:  # HU0014-1
        _err(422, "Confirma que revisaste las referencias antes de insertarlas.", codigo="confirmar_revision")

    secciones = [dict(s) for s in (r.borrador.contenido or {}).get("secciones", [])]
    por_id = {s["id"]: s for s in secciones}
    for cambio in m.propuesta.get("secciones", []):
        destino = por_id.get(cambio.get("id"))
        if destino:
            if cambio.get("titulo"):
                destino["titulo"] = cambio["titulo"]
            destino["html"] = cambio.get("html", destino["html"])
        else:
            secciones.append({"id": "s" + uuid.uuid4().hex[:8], "clave": None,
                              "titulo": cambio.get("titulo") or "Nueva sección", "html": cambio.get("html", "")})
    conf = guardar_contenido(db, r, secciones)
    m.aplicado = True
    db.commit()
    return {"ok": True, "contenido": {"secciones": secciones}, "conformidad": conf, "estado": r.estado,
            "fecha_guardado": r.borrador.fecha_guardado}
