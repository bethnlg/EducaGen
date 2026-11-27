"""Monitoreo y auditoría (RF-07, RF-08, I-12)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Alerta, ConsultaLLM, ConsultaMaterial
from .llm.base import Uso


def registrar_consulta(db: Session, *, id_usuario: int, id_recurso: int | None, operacion: str, uso: Uso | None,
                       estado: str, materiales: list | None = None, tokens_salida: int | None = None) -> ConsultaLLM:
    uso = uso or Uso()
    consulta = ConsultaLLM(
        id_usuario=id_usuario,
        id_recurso=id_recurso,
        proveedor=(uso.proveedor or "ninguno")[:40],
        modelo=(uso.modelo or "-")[:120],
        tipo_operacion=operacion[:40],
        tokens_entrada=uso.tokens_entrada,
        tokens_salida=tokens_salida if tokens_salida is not None else uso.tokens_salida,
        tiempo_respuesta_ms=uso.tiempo_ms or None,
        numero_reintentos=uso.reintentos,
        fue_conmutada=uso.conmutada,
        estado=estado,
    )
    db.add(consulta)
    db.flush()
    for m in materiales or []:
        db.add(ConsultaMaterial(id_consulta=consulta.id_consulta, id_material=m.id_material))
    return consulta


def crear_alerta(db: Session, *, id_usuario: int, tipo: str, severidad: str, titulo: str, descripcion: str,
                 id_recurso: int | None = None, id_consulta: int | None = None, unica: bool = True) -> Alerta:
    """Crea una alerta; si unica=True y ya existe una activa del mismo tipo y recurso, la actualiza."""
    if unica:
        existente = db.scalar(
            select(Alerta).where(
                Alerta.id_usuario == id_usuario, Alerta.tipo == tipo, Alerta.id_recurso == id_recurso, Alerta.atendida.is_(False)
            )
        )
        if existente:
            existente.titulo, existente.descripcion, existente.severidad = titulo, descripcion[:300], severidad
            return existente
    alerta = Alerta(id_usuario=id_usuario, id_recurso=id_recurso, id_consulta=id_consulta, tipo=tipo,
                    severidad=severidad, titulo=titulo[:120], descripcion=descripcion[:300])
    db.add(alerta)
    return alerta


def cerrar_alertas(db: Session, *, id_usuario: int, id_recurso: int, tipo: str):
    for a in db.scalars(select(Alerta).where(Alerta.id_usuario == id_usuario, Alerta.id_recurso == id_recurso,
                                             Alerta.tipo == tipo, Alerta.atendida.is_(False))):
        a.atendida = True


def sincronizar_alerta_conformidad(db: Session, recurso, conformidad: dict):
    """HU0024-2 / panel de calidad: mantiene una alerta por recurso con secciones faltantes."""
    if conformidad["conforme"]:
        cerrar_alertas(db, id_usuario=recurso.id_usuario, id_recurso=recurso.id_recurso, tipo="seccion_faltante")
    else:
        faltan = ", ".join(conformidad["faltantes"]).lower()
        crear_alerta(
            db, id_usuario=recurso.id_usuario, id_recurso=recurso.id_recurso, tipo="seccion_faltante", severidad="media",
            titulo="Sección faltante detectada",
            descripcion=f"«{recurso.titulo}» no incluye: {faltan}.",
        )
