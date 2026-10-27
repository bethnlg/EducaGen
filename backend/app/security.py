"""Autenticación (RNF-01): bcrypt para contraseñas y JWT de corta duración."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import config

COOKIE_SESION = "session"


def hash_contrasena(contrasena: str) -> str:
    return bcrypt.hashpw(contrasena.encode("utf-8")[:72], bcrypt.gensalt(rounds=10)).decode("utf-8")


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8")[:72], hash_guardado.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def crear_token(usuario) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id_usuario),
        "id": usuario.id_usuario,
        "nombre": usuario.nombre_completo,
        "correo": usuario.correo_institucional,
        "rol": usuario.rol.nombre if usuario.rol else "docente",
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(hours=config.JWT_HORAS)).timestamp()),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def leer_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def nuevo_token_recuperacion() -> tuple[str, str]:
    """Devuelve (token en claro para el enlace, hash que se guarda en la BD)."""
    token = secrets.token_hex(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
