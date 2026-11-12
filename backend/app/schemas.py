"""Esquemas de validación de las solicitudes (Seguridad de APIs, Tabla 9)."""
from typing import Optional

from pydantic import BaseModel, Field


class ArchivoAdjuntoIn(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    nombre: str = Field(min_length=1, max_length=200)
    tipo: str = Field(default="application/octet-stream", max_length=150)
    tamano: int = Field(ge=0)
    texto: str = Field(default="", max_length=12000)


class RegistroIn(BaseModel):
    nombre: str = Field(default="", max_length=200)
    correo: str = Field(default="", max_length=150)
    contrasena: str = Field(default="", max_length=200)


class LoginIn(BaseModel):
    correo: str = Field(default="", max_length=150)
    contrasena: str = Field(default="", max_length=200)


class OlvidoIn(BaseModel):
    correo: str = Field(default="", max_length=150)


class RestablecerIn(BaseModel):
    correo: str = Field(default="", max_length=150)
    token: str = Field(default="", max_length=200)
    contrasena: str = Field(default="", max_length=200)


class GenerarIn(BaseModel):
    tipo: str = "silabo"
    curso: str = Field(default="", max_length=150)
    temas: str = Field(default="", max_length=2000)
    carrera: Optional[str] = Field(default=None, max_length=120)
    ciclo: Optional[int] = Field(default=None, ge=1, le=12)
    semanas: Optional[int] = Field(default=None, ge=1, le=24)
    niveles: Optional[str] = Field(default=None, max_length=300)
    num_preguntas: Optional[int] = Field(default=None, ge=1, le=200)
    sector: Optional[str] = Field(default=None, max_length=80)
    forzar: bool = False
    aceptar_propuesta: bool = False
    adjuntos: list[ArchivoAdjuntoIn] = Field(default_factory=list, max_length=5)


class BorradorIn(BaseModel):
    contenido: Optional[dict] = None
    titulo: Optional[str] = Field(default=None, max_length=200)
    segundos_activos: int = Field(default=0, ge=0, le=3600)


class RegenerarIn(BaseModel):
    seccion_id: str
    bloque_html: str = Field(max_length=20000)
    instruccion: str = Field(default="", max_length=400)
    intento: int = 1


class AsistenteIn(BaseModel):
    mensaje: str = Field(default="", max_length=2000)
    secciones: Optional[list[dict]] = None
    adjuntos: list[ArchivoAdjuntoIn] = Field(default_factory=list, max_length=5)


class AplicarIn(BaseModel):
    confirmado: bool = False


class EvaluacionIn(BaseModel):
    id_recurso: int
    nota_ia: float = Field(ge=0, le=20)
    nota_final: float = Field(ge=0, le=20)
    observaciones: str = Field(default="", max_length=1000)


class SugerirNotaIn(BaseModel):
    id_recurso: int
    respuesta: str = Field(min_length=20, max_length=12000)
