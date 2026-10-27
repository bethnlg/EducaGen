"""Panel de calidad: conformidad, alertas, tiempos de la IA y comparación de notas."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import obtener_recurso_propio, usuario_actual
from ..models import Alerta, AuditoriaCalidad, ConsultaLLM, RecursoEducativo, RegistroEdicion, TiempoElaboracion, Usuario
from ..schemas import EvaluacionIn, SugerirNotaIn
from ..services.esquemas import contenido_a_texto, verificar_conformidad
from ..services.llm import SinProveedoresError, adaptador
from ..services.monitoreo import crear_alerta, registrar_consulta
from ..services.prompts import extraer_json, prompt_calificacion

router = APIRouter(prefix="/api/calidad", tags=["calidad"])

TIPOS_EVALUABLES = {"rubrica", "examen", "caso"}


def _err(codigo: int, mensaje: str):
    raise HTTPException(codigo, detail={"mensaje": mensaje})


def _aware(f):
    from datetime import timezone

    return f if f is None or f.tzinfo else f.replace(tzinfo=timezone.utc)


@router.get("")
def panel(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    recursos = db.scalars(select(RecursoEducativo).where(RecursoEducativo.id_usuario == usuario.id_usuario,
                                                         RecursoEducativo.fecha_eliminacion.is_(None))).all()
    porcentajes, auditados = [], 0
    for r in recursos:
        secciones = (r.borrador.contenido or {}).get("secciones", []) if r.borrador else []
        if secciones:
            porcentajes.append(verificar_conformidad(r.tipo.clave, secciones)["porcentaje"])
            auditados += 1
    conformidad = round(sum(porcentajes) / len(porcentajes), 1) if porcentajes else None

    tiempo_medio = db.scalar(select(func.avg(ConsultaLLM.tiempo_respuesta_ms)).where(
        ConsultaLLM.id_usuario == usuario.id_usuario, ConsultaLLM.estado == "exitosa"))
    consultas = db.scalar(select(func.count(ConsultaLLM.id_consulta)).where(ConsultaLLM.id_usuario == usuario.id_usuario)) or 0
    conmutadas = db.scalar(select(func.count(ConsultaLLM.id_consulta)).where(ConsultaLLM.id_usuario == usuario.id_usuario,
                                                                            ConsultaLLM.fue_conmutada.is_(True))) or 0
    tokens = db.scalar(select(func.coalesce(func.sum(ConsultaLLM.tokens_entrada + ConsultaLLM.tokens_salida), 0)).where(
        ConsultaLLM.id_usuario == usuario.id_usuario)) or 0

    alertas = db.scalars(select(Alerta).where(Alerta.id_usuario == usuario.id_usuario)
                         .order_by(Alerta.atendida, Alerta.fecha_alerta.desc()).limit(12)).all()
    activas = db.scalar(select(func.count(Alerta.id_alerta)).where(Alerta.id_usuario == usuario.id_usuario, Alerta.atendida.is_(False))) or 0

    # Indicadores de elaboración (insumo para la medición pretest/postest del Objetivo 4)
    aprobados = [r for r in recursos if r.estado == "aprobado"]
    ids_aprobados = [r.id_recurso for r in aprobados]
    minutos = None
    editado = None
    if ids_aprobados:
        seg = db.scalar(select(func.avg(TiempoElaboracion.segundos_activos)).where(TiempoElaboracion.id_recurso.in_(ids_aprobados)))
        minutos = round((seg or 0) / 60, 1)
        pct = db.scalar(select(func.avg(RegistroEdicion.porcentaje_modificado)).where(RegistroEdicion.id_recurso.in_(ids_aprobados)))
        editado = round(float(pct), 1) if pct is not None else None

    filas = db.execute(
        select(AuditoriaCalidad, RecursoEducativo).join(RecursoEducativo, RecursoEducativo.id_recurso == AuditoriaCalidad.id_recurso)
        .where(AuditoriaCalidad.id_auditor == usuario.id_usuario, AuditoriaCalidad.nota_final.is_not(None))
        .order_by(AuditoriaCalidad.fecha_auditoria.desc()).limit(50)
    ).all()
    notas = [{
        "id": a.id_auditoria, "recurso": r.titulo, "id_recurso": r.id_recurso, "tipo": r.tipo.clave, "tipo_nombre": r.tipo.nombre,
        "nota_ia": float(a.nota_ia) if a.nota_ia is not None else None, "nota_final": float(a.nota_final),
        "diferencia": round(float(a.nota_final) - float(a.nota_ia), 1) if a.nota_ia is not None else None,
        "fecha": _aware(a.fecha_auditoria),
    } for a, r in filas]

    evaluables = [{"id": r.id_recurso, "titulo": r.titulo, "tipo": r.tipo.clave} for r in recursos if r.tipo.clave in TIPOS_EVALUABLES and r.borrador and (r.borrador.contenido or {}).get("secciones")]

    return {
        "indicadores": {
            "conformidad": conformidad,
            "recursos_auditados": auditados,
            "alertas_activas": activas,
            "tiempo_medio_ia_seg": round(float(tiempo_medio) / 1000, 1) if tiempo_medio else None,
            "consultas_ia": consultas,
            "consultas_conmutadas": conmutadas,
            "tokens_totales": int(tokens),
            "recursos_aprobados": len(aprobados),
            "minutos_medios_elaboracion": minutos,
            "porcentaje_medio_editado": editado,
        },
        "alertas": [{"id": a.id_alerta, "tipo": a.tipo, "severidad": a.severidad, "titulo": a.titulo, "descripcion": a.descripcion,
                     "atendida": a.atendida, "id_recurso": a.id_recurso, "fecha": _aware(a.fecha_alerta)} for a in alertas],
        "notas": notas,
        "recursos_evaluables": evaluables,
        "ia": adaptador.descripcion(),
    }


@router.patch("/alertas/{id_alerta}")
def atender_alerta(id_alerta: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    alerta = db.get(Alerta, id_alerta)
    if not alerta or alerta.id_usuario != usuario.id_usuario:
        _err(404, "La alerta no existe.")
    alerta.atendida = True
    db.commit()
    return {"ok": True}


@router.post("/evaluaciones", status_code=201)
def registrar_evaluacion(datos: EvaluacionIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """HU0026: el docente registra la nota sugerida por la IA y su nota final."""
    r = obtener_recurso_propio(db, datos.id_recurso, usuario)
    if r.tipo.clave not in TIPOS_EVALUABLES:
        _err(422, "Solo se registran notas de rúbricas, exámenes o casos de estudio.")
    diferencia = round(datos.nota_final - datos.nota_ia, 1)
    db.add(AuditoriaCalidad(
        id_recurso=r.id_recurso, id_auditor=usuario.id_usuario, nota_ia=datos.nota_ia, nota_final=datos.nota_final,
        tasa_exactitud=round(max(0.0, 100 - abs(diferencia) / 20 * 100), 2),
        numero_inconsistencias=1 if abs(diferencia) >= 2 else 0, observaciones=datos.observaciones or None,
    ))
    db.flush()
    # Diferencia recurrente: 3 evaluaciones seguidas del mismo curso con 2 o más puntos de diferencia
    ultimas = db.scalars(select(AuditoriaCalidad).join(RecursoEducativo, RecursoEducativo.id_recurso == AuditoriaCalidad.id_recurso)
                         .where(AuditoriaCalidad.id_auditor == usuario.id_usuario, RecursoEducativo.id_curso == r.id_curso,
                                AuditoriaCalidad.nota_ia.is_not(None))
                         .order_by(AuditoriaCalidad.fecha_auditoria.desc(), AuditoriaCalidad.id_auditoria.desc()).limit(3)).all()
    if len(ultimas) == 3 and all(abs(float(a.nota_final) - float(a.nota_ia)) >= 2 for a in ultimas):
        crear_alerta(db, id_usuario=usuario.id_usuario, id_recurso=r.id_recurso, tipo="diferencia_notas", severidad="alta",
                     titulo=f"Diferencia recurrente en {r.curso.nombre}",
                     descripcion=f"Tu nota final difiere de la sugerencia de la IA en {len(ultimas)} evaluaciones consecutivas de {r.curso.nombre}.")
    db.commit()
    return {"ok": True, "diferencia": diferencia}


@router.post("/sugerir-nota")
async def sugerir_nota(datos: SugerirNotaIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Aplica la rúbrica o clave del recurso a una respuesta anónima para sugerir una nota."""
    r = obtener_recurso_propio(db, datos.id_recurso, usuario)
    if r.tipo.clave not in TIPOS_EVALUABLES:
        _err(422, "Elige una rúbrica, un examen o un caso de estudio.")
    texto = contenido_a_texto({"secciones": (r.borrador.contenido or {}).get("secciones", [])})
    try:
        respuesta, uso = await adaptador.completar(prompt_calificacion(texto, datos.respuesta))
    except SinProveedoresError:
        _err(503, "Los servicios de IA no están disponibles en este momento.")
    registrar_consulta(db, id_usuario=usuario.id_usuario, id_recurso=r.id_recurso, operacion="calificacion", uso=uso, estado="exitosa")
    db.commit()
    resultado = extraer_json(respuesta) or {}
    try:
        nota = max(0.0, min(20.0, float(resultado.get("nota"))))
    except (TypeError, ValueError):
        _err(502, "La IA no devolvió una nota válida. Vuelve a intentarlo.")
    return {"nota": round(nota, 1), "justificacion": str(resultado.get("justificacion") or "")[:600]}

