"""Entidades de la capa de datos (Figura 6 del OB2: diagrama físico)."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base, JSONType


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Rol(Base):
    __tablename__ = "rol"
    id_rol: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30), unique=True)
    descripcion: Mapped[Optional[str]] = mapped_column(String(150))


class Usuario(Base):
    __tablename__ = "usuario"
    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_rol: Mapped[int] = mapped_column(ForeignKey("rol.id_rol"))
    nombres: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(100), default="")
    correo_institucional: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    estado: Mapped[str] = mapped_column(String(20), default="activo")
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    ultimo_acceso: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    rol: Mapped[Rol] = relationship()

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()


class TokenRecuperacion(Base):
    __tablename__ = "token_recuperacion"
    id_token: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(255), index=True)
    fecha_expiracion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado: Mapped[bool] = mapped_column(Boolean, default=False)


class TokenVerificacion(Base):
    __tablename__ = "token_verificacion"
    id_token: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(255), index=True)
    fecha_expiracion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado: Mapped[bool] = mapped_column(Boolean, default=False)


class Carrera(Base):
    __tablename__ = "carrera"
    id_carrera: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)


class Curso(Base):
    __tablename__ = "curso"
    id_curso: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_carrera: Mapped[Optional[int]] = mapped_column(ForeignKey("carrera.id_carrera"))
    codigo: Mapped[Optional[str]] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(150))
    ciclo: Mapped[Optional[int]] = mapped_column(SmallInteger)

    carrera: Mapped[Optional[Carrera]] = relationship()


class TipoRecurso(Base):
    __tablename__ = "tipo_recurso"
    id_tipo_recurso: Mapped[int] = mapped_column(Integer, primary_key=True)
    clave: Mapped[str] = mapped_column(String(20), unique=True)  # silabo, rubrica, examen, caso
    nombre: Mapped[str] = mapped_column(String(40))
    esquema_estructura: Mapped[dict] = mapped_column(JSONType, default=dict)


class RecursoEducativo(Base):
    __tablename__ = "recurso_educativo"
    id_recurso: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"), index=True)
    id_curso: Mapped[int] = mapped_column(ForeignKey("curso.id_curso"))
    id_tipo_recurso: Mapped[int] = mapped_column(ForeignKey("tipo_recurso.id_tipo_recurso"))
    id_recurso_origen: Mapped[Optional[int]] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="SET NULL"))
    titulo: Mapped[str] = mapped_column(String(200))
    # generando | borrador | pendiente (IA no disponible) | aprobado
    estado: Mapped[str] = mapped_column(String(20), default="borrador")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    fecha_aprobacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_eliminacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    curso: Mapped[Curso] = relationship()
    tipo: Mapped[TipoRecurso] = relationship()
    borrador: Mapped[Optional["Borrador"]] = relationship(back_populates="recurso", uselist=False, cascade="all, delete-orphan")
    versiones: Mapped[list["VersionRecurso"]] = relationship(back_populates="recurso", cascade="all, delete-orphan", order_by="VersionRecurso.numero_version")
    tiempo: Mapped[Optional["TiempoElaboracion"]] = relationship(uselist=False, cascade="all, delete-orphan")


class Borrador(Base):
    __tablename__ = "borrador"
    id_borrador: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_recurso: Mapped[int] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="CASCADE"), unique=True)
    contenido: Mapped[dict] = mapped_column(JSONType, default=dict)
    fecha_guardado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    recurso: Mapped[RecursoEducativo] = relationship(back_populates="borrador")


class VersionRecurso(Base):
    __tablename__ = "version_recurso"
    __table_args__ = (UniqueConstraint("id_recurso", "numero_version"),)
    id_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_recurso: Mapped[int] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="CASCADE"))
    numero_version: Mapped[int] = mapped_column(Integer)
    contenido: Mapped[dict] = mapped_column(JSONType, default=dict)
    origen: Mapped[str] = mapped_column(String(20))  # ia | docente
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    recurso: Mapped[RecursoEducativo] = relationship(back_populates="versiones")


class ValidacionEstructura(Base):
    __tablename__ = "validacion_estructura"
    id_validacion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_version: Mapped[int] = mapped_column(ForeignKey("version_recurso.id_version", ondelete="CASCADE"))
    conforme: Mapped[bool] = mapped_column(Boolean)
    secciones_faltantes: Mapped[list] = mapped_column(JSONType, default=list)
    fecha_validacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class RegistroEdicion(Base):
    __tablename__ = "registro_edicion"
    id_registro: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_recurso: Mapped[int] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="CASCADE"))
    id_version_ia: Mapped[int] = mapped_column(ForeignKey("version_recurso.id_version"))
    id_version_final: Mapped[int] = mapped_column(ForeignKey("version_recurso.id_version"))
    porcentaje_modificado: Mapped[float] = mapped_column(Numeric(5, 2))
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class TiempoElaboracion(Base):
    __tablename__ = "tiempo_elaboracion"
    id_tiempo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_recurso: Mapped[int] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="CASCADE"), unique=True)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    fecha_aprobacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    segundos_activos: Mapped[int] = mapped_column(Integer, default=0)
    numero_ediciones: Mapped[int] = mapped_column(Integer, default=0)


class ArchivoExportado(Base):
    __tablename__ = "archivo_exportado"
    id_archivo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_recurso: Mapped[int] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="CASCADE"))
    id_version: Mapped[Optional[int]] = mapped_column(ForeignKey("version_recurso.id_version", ondelete="SET NULL"))
    formato: Mapped[str] = mapped_column(String(10))
    incluye_membrete: Mapped[bool] = mapped_column(Boolean, default=False)
    ruta_s3: Mapped[str] = mapped_column(String(500))
    fecha_expiracion_enlace: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_exportacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class ArchivoAdjunto(Base):
    __tablename__ = "archivo_adjunto"
    id_archivo: Mapped[str] = mapped_column(String(80), primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"), index=True)
    id_recurso: Mapped[Optional[int]] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(150), default="application/octet-stream")
    tamano: Mapped[int] = mapped_column(Integer)
    ruta: Mapped[str] = mapped_column(String(500))
    texto: Mapped[str] = mapped_column(Text, default="")
    texto_extraido: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_carga: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class MaterialModelo(Base):
    __tablename__ = "material_modelo"
    id_material: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_tipo_recurso: Mapped[int] = mapped_column(ForeignKey("tipo_recurso.id_tipo_recurso"))
    id_carrera: Mapped[Optional[int]] = mapped_column(ForeignKey("carrera.id_carrera"))
    id_usuario_carga: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="SET NULL"))
    ciclo: Mapped[Optional[int]] = mapped_column(SmallInteger)
    titulo: Mapped[str] = mapped_column(String(200))
    contenido_texto: Mapped[str] = mapped_column(Text)
    ruta_archivo: Mapped[Optional[str]] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(20), default="validado")
    fecha_carga: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    carrera: Mapped[Optional[Carrera]] = relationship()


class ConsultaLLM(Base):
    __tablename__ = "consulta_llm"
    id_consulta: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_recurso: Mapped[Optional[int]] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="SET NULL"))
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"), index=True)
    proveedor: Mapped[str] = mapped_column(String(20))
    modelo: Mapped[str] = mapped_column(String(60))
    tipo_operacion: Mapped[str] = mapped_column(String(20))  # generacion | asistente | regeneracion | calificacion
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0)
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0)
    tiempo_respuesta_ms: Mapped[Optional[int]] = mapped_column(Integer)
    numero_reintentos: Mapped[int] = mapped_column(SmallInteger, default=0)
    fue_conmutada: Mapped[bool] = mapped_column(Boolean, default=False)
    estado: Mapped[str] = mapped_column(String(20))  # exitosa | fallida | detenida
    fecha_consulta: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class ConsultaMaterial(Base):
    __tablename__ = "consulta_material"
    id_consulta: Mapped[int] = mapped_column(ForeignKey("consulta_llm.id_consulta", ondelete="CASCADE"), primary_key=True)
    id_material: Mapped[int] = mapped_column(ForeignKey("material_modelo.id_material", ondelete="CASCADE"), primary_key=True)


class Alerta(Base):
    __tablename__ = "alerta"
    id_alerta: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"), index=True)
    id_recurso: Mapped[Optional[int]] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="CASCADE"))
    id_consulta: Mapped[Optional[int]] = mapped_column(ForeignKey("consulta_llm.id_consulta", ondelete="SET NULL"))
    tipo: Mapped[str] = mapped_column(String(40))
    severidad: Mapped[str] = mapped_column(String(10))  # alta | media | baja
    titulo: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str] = mapped_column(String(300))
    atendida: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_alerta: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AuditoriaCalidad(Base):
    __tablename__ = "auditoria_calidad"
    id_auditoria: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_recurso: Mapped[int] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="CASCADE"))
    id_auditor: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"))
    tasa_exactitud: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    numero_inconsistencias: Mapped[int] = mapped_column(Integer, default=0)
    nota_ia: Mapped[Optional[float]] = mapped_column(Numeric(4, 1))
    nota_final: Mapped[Optional[float]] = mapped_column(Numeric(4, 1))
    observaciones: Mapped[Optional[str]] = mapped_column(Text)
    fecha_auditoria: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class MensajeAsistente(Base):
    __tablename__ = "mensaje_asistente"
    id_mensaje: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_recurso: Mapped[int] = mapped_column(ForeignKey("recurso_educativo.id_recurso", ondelete="CASCADE"), index=True)
    emisor: Mapped[str] = mapped_column(String(20))  # docente | asistente
    contenido: Mapped[str] = mapped_column(Text)
    propuesta: Mapped[Optional[dict]] = mapped_column(JSONType)
    aplicado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_envio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
