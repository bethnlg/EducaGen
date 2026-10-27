"""Dependencias comunes: usuario autenticado (JWT) y regla de acceso HU0004."""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import RecursoEducativo, Usuario
from .security import COOKIE_SESION, leer_token


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    token = request.cookies.get(COOKIE_SESION)
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    datos = leer_token(token) if token else None
    if not datos:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"mensaje": "Tu sesión expiró. Vuelve a iniciar sesión."})
    usuario = db.get(Usuario, int(datos["sub"]))
    if not usuario or usuario.estado != "activo":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"mensaje": "Tu sesión expiró. Vuelve a iniciar sesión."})
    return usuario


def obtener_recurso_propio(db: Session, id_recurso: int, usuario: Usuario, incluir_eliminados: bool = False) -> RecursoEducativo:
    """HU0004: solo el docente dueño puede ver y modificar su recurso (403 en caso contrario)."""
    recurso = db.get(RecursoEducativo, id_recurso)
    if not recurso or (recurso.fecha_eliminacion is not None and not incluir_eliminados):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"mensaje": "El recurso no existe o fue eliminado."})
    if recurso.id_usuario != usuario.id_usuario:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"mensaje": "Acceso denegado: este recurso pertenece a otro docente."})
    return recurso
