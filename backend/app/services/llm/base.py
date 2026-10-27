"""Interfaz común del adaptador de proveedores (I-04, DA-05)."""
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class Solicitud:
    sistema: str
    prompt: str
    operacion: str  # generacion | asistente | regeneracion | calificacion
    json: bool = False
    temperatura: float = 0.6
    max_tokens: int = 8192
    # Datos estructurados que solo usa el proveedor de demostración
    contexto: dict = field(default_factory=dict)


@dataclass
class Uso:
    proveedor: str = ""
    modelo: str = ""
    tokens_entrada: int = 0
    tokens_salida: int = 0
    tiempo_ms: int = 0
    reintentos: int = 0
    conmutada: bool = False


class ProveedorError(Exception):
    """Error de un proveedor. transitorio=True permite reintentar (timeouts, 429, 5xx)."""

    def __init__(self, mensaje: str, transitorio: bool = True):
        super().__init__(mensaje)
        self.transitorio = transitorio


class SinProveedoresError(Exception):
    """Ningún proveedor de IA respondió (HU0029-2)."""


class Proveedor:
    nombre = "base"
    modelo = ""

    def disponible(self) -> bool:
        return True

    async def stream(self, sol: Solicitud, uso: Uso) -> AsyncIterator[str]:  # pragma: no cover
        raise NotImplementedError
        yield ""


def estimar_tokens(texto: str) -> int:
    return max(1, len(texto or "") // 4)
