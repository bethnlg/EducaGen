"""Gestión de usuarios y acceso: registro, inicio de sesión y recuperación de contraseña."""
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import config
from ..database import get_db
from ..deps import usuario_actual
from ..models import TokenRecuperacion, Usuario
from ..schemas import LoginIn, OlvidoIn, RegistroIn, RestablecerIn
from ..security import COOKIE_SESION, crear_token, hash_contrasena, hash_token, nuevo_token_recuperacion, verificar_contrasena
from ..services import correo

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("educagen.auth")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _err(codigo: int, mensaje: str, **extra):
    raise HTTPException(codigo, detail={"mensaje": mensaje, **extra})


def _poner_cookie(respuesta: Response, usuario: Usuario):
    respuesta.set_cookie(
        COOKIE_SESION, crear_token(usuario), httponly=True, secure=config.COOKIE_SEGURA,
        samesite="lax", path="/", max_age=config.JWT_HORAS * 3600,
    )


def _perfil(u: Usuario) -> dict:
    return {"id": u.id_usuario, "nombre": u.nombre_completo, "correo": u.correo_institucional, "rol": u.rol.nombre if u.rol else "docente"}


@router.post("/register", status_code=201)
def registrar(datos: RegistroIn, respuesta: Response, tareas: BackgroundTasks, db: Session = Depends(get_db)):
    nombre, correo_n = datos.nombre.strip(), datos.correo.strip().lower()
    faltan = [c for c, v in (("nombre", nombre), ("correo", correo_n), ("contrasena", datos.contrasena)) if not v]
    if faltan:
        _err(400, "Completa todos los campos.", campos=faltan)
    if not EMAIL_RE.match(correo_n):
        _err(400, "Ingresa un correo válido.", campos=["correo"])
    if len(datos.contrasena) < 8:
        _err(400, "La contraseña debe tener al menos 8 caracteres.", campos=["contrasena"])
    if db.scalar(select(Usuario).where(Usuario.correo_institucional == correo_n)):  # HU0001-2
        _err(409, "Este correo ya se encuentra en uso. Inicia sesión o recupera tu contraseña.", campos=["correo"])

    partes = nombre.split(" ", 1)
    usuario = Usuario(id_rol=1, nombres=partes[0], apellidos=partes[1] if len(partes) > 1 else "",
                      correo_institucional=correo_n, hash_contrasena=hash_contrasena(datos.contrasena),
                      ultimo_acceso=datetime.now(timezone.utc))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    _poner_cookie(respuesta, usuario)
    tareas.add_task(_enviar_seguro, correo.enviar_bienvenida, correo_n, usuario.nombre_completo)  # HU0001-1
    return {"ok": True, "usuario": _perfil(usuario)}


@router.post("/login")
def iniciar_sesion(datos: LoginIn, respuesta: Response, db: Session = Depends(get_db)):
    correo_n = datos.correo.strip().lower()
    if not correo_n or not datos.contrasena:
        _err(400, "Ingresa tu correo y contraseña.")
    usuario = db.scalar(select(Usuario).where(Usuario.correo_institucional == correo_n))
    if not usuario or usuario.estado != "activo" or not verificar_contrasena(datos.contrasena, usuario.hash_contrasena):
        _err(401, "El correo o la contraseña no son correctos.")  # HU0002-2: mensaje general
    usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.commit()
    _poner_cookie(respuesta, usuario)
    return {"ok": True, "usuario": _perfil(usuario)}


@router.post("/logout")
def cerrar_sesion(respuesta: Response):
    respuesta.delete_cookie(COOKIE_SESION, path="/")
    return {"ok": True}


@router.get("/me")
def yo(usuario: Usuario = Depends(usuario_actual)):
    return _perfil(usuario)


@router.post("/forgot")
def olvido(datos: OlvidoIn, tareas: BackgroundTasks, db: Session = Depends(get_db)):
    correo_n = datos.correo.strip().lower()
    if not EMAIL_RE.match(correo_n):
        _err(400, "Ingresa un correo válido.")
    usuario = db.scalar(select(Usuario).where(Usuario.correo_institucional == correo_n))
    # HU0003-2: la respuesta es idéntica exista o no la cuenta
    if usuario:
        for t in db.scalars(select(TokenRecuperacion).where(TokenRecuperacion.id_usuario == usuario.id_usuario, TokenRecuperacion.usado.is_(False))):
            t.usado = True
        token, token_hash = nuevo_token_recuperacion()
        db.add(TokenRecuperacion(id_usuario=usuario.id_usuario, token_hash=token_hash,
                                 fecha_expiracion=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
        enlace = f"{config.APP_URL}/restablecer?correo={correo_n}&token={token}"
        tareas.add_task(_enviar_seguro, correo.enviar_recuperacion, correo_n, usuario.nombre_completo, enlace)
    return {"ok": True, "mensaje": "Si existe una cuenta con ese correo, recibirás un enlace para restablecer tu contraseña."}


@router.post("/reset")
def restablecer(datos: RestablecerIn, db: Session = Depends(get_db)):
    if not datos.correo or not datos.token or not datos.contrasena:
        _err(400, "Faltan datos. Abre de nuevo el enlace del correo.")
    if len(datos.contrasena) < 8:
        _err(400, "La contraseña debe tener al menos 8 caracteres.")
    usuario = db.scalar(select(Usuario).where(Usuario.correo_institucional == datos.correo.strip().lower()))
    token = None
    if usuario:
        token = db.scalar(select(TokenRecuperacion).where(
            TokenRecuperacion.id_usuario == usuario.id_usuario,
            TokenRecuperacion.token_hash == hash_token(datos.token),
            TokenRecuperacion.usado.is_(False),
        ))
    ahora = datetime.now(timezone.utc)
    if not token or _aware(token.fecha_expiracion) < ahora:
        _err(400, "El enlace no es válido o ya venció. Solicita uno nuevo.")
    usuario.hash_contrasena = hash_contrasena(datos.contrasena)
    token.usado = True
    db.commit()
    return {"ok": True}


def _aware(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _enviar_seguro(funcion, *args):
    try:
        funcion(*args)
    except Exception as e:  # el error de correo no debe romper el flujo
        log.error("No se pudo enviar el correo: %s", e)
