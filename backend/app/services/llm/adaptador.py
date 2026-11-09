"""Adaptador de proveedores (DA-05, RNF-03, HU0028, HU0029).

- Tiempo máximo de espera por solicitud (en cada proveedor).
- Reintentos con espera exponencial ante errores transitorios (3 en el principal).
- Conmutación automática al proveedor de respaldo (Claude).
- Interruptor de circuito: tras N fallas consecutivas del principal, las
  solicitudes van directo al respaldo durante un periodo; luego pasa a
  semiabierto y prueba de nuevo el principal.
"""
import asyncio
import logging
import time
from typing import AsyncIterator

from ...config import config
from .base import Proveedor, ProveedorError, SinProveedoresError, Solicitud, Uso
from .demo import DemoProveedor
from .proveedores import GeminiProveedor, LlamaProveedor

log = logging.getLogger("educagen.llm")


class InterruptorCircuito:
    def __init__(self, umbral: int, espera_seg: int):
        self.umbral = umbral
        self.espera = espera_seg
        self.fallas = 0
        self.abierto_desde: float | None = None

    @property
    def estado(self) -> str:
        if self.abierto_desde is None:
            return "cerrado"
        if time.monotonic() - self.abierto_desde >= self.espera:
            return "semiabierto"
        return "abierto"

    def permite(self) -> bool:
        return self.estado != "abierto"

    def exito(self):
        self.fallas = 0
        self.abierto_desde = None

    def falla(self):
        self.fallas += 1
        if self.fallas >= self.umbral or self.estado == "semiabierto":
            self.abierto_desde = time.monotonic()
            log.warning("Interruptor de circuito ABIERTO para el proveedor principal")


class Evento:
    """Eventos emitidos durante el streaming."""

    def __init__(self, tipo: str, texto: str = "", uso: Uso | None = None, proveedor: str = ""):
        self.tipo = tipo  # chunk | reinicio | fin
        self.texto = texto
        self.uso = uso
        self.proveedor = proveedor


class AdaptadorLLM:
    def __init__(self):
        self.circuito = InterruptorCircuito(config.CIRCUITO_FALLAS, config.CIRCUITO_ESPERA_SEG)

    def _proveedores(self) -> tuple[Proveedor | None, Proveedor | None]:
        gemini, llama = GeminiProveedor(), LlamaProveedor()
        modo_demo = config.LLM_MODO == "demo" or not (gemini.disponible() or llama.disponible())
        if modo_demo:
            principal = DemoProveedor("gemini-demo", fallar=config.LLM_SIMULAR_FALLA_PRINCIPAL or config.LLM_SIMULAR_FALLA_TOTAL)
            respaldo = DemoProveedor("llama-demo", fallar=config.LLM_SIMULAR_FALLA_TOTAL)
            return principal, respaldo
        principal = llama if llama.disponible() else None
        respaldo = gemini if gemini.disponible() else None
        if principal is None:
            principal, respaldo = respaldo, None
        return principal, respaldo

    def descripcion(self) -> dict:
        principal, respaldo = self._proveedores()
        return {
            "principal": principal.nombre if principal else None,
            "respaldo": respaldo.nombre if respaldo else None,
            "circuito": self.circuito.estado,
        }

    async def stream(self, sol: Solicitud) -> AsyncIterator[Evento]:
        principal, respaldo = self._proveedores()
        orden: list[tuple[Proveedor, int, bool]] = []
        if principal and self.circuito.permite():
            orden.append((principal, max(1, config.LLM_REINTENTOS), True))
        if respaldo:
            orden.append((respaldo, 2, False))
        if not orden and principal:  # circuito abierto y sin respaldo: se intenta igual
            orden.append((principal, 1, True))

        total_reintentos = 0
        conmutada = False
        ultimo_error = "sin proveedores configurados"
        for indice, (prov, intentos, es_principal) in enumerate(orden):
            if indice > 0 or not es_principal:
                conmutada = conmutada or (principal is not None and prov is not principal)
            for intento in range(intentos):
                uso = Uso()
                emitio = False
                inicio = time.monotonic()
                try:
                    async for texto in prov.stream(sol, uso):
                        emitio = True
                        yield Evento("chunk", texto)
                    uso.tiempo_ms = int((time.monotonic() - inicio) * 1000)
                    uso.reintentos = total_reintentos
                    uso.conmutada = conmutada
                    if es_principal:
                        self.circuito.exito()
                    yield Evento("fin", uso=uso, proveedor=prov.nombre)
                    return
                except ProveedorError as e:
                    ultimo_error = str(e)
                    log.warning("Falla en %s (intento %s/%s): %s", prov.nombre, intento + 1, intentos, e)
                    if emitio:
                        yield Evento("reinicio", proveedor=prov.nombre)
                    total_reintentos += 1
                    if not e.transitorio:
                        break
                    if intento < intentos - 1:
                        await asyncio.sleep(0.5 * (2 ** intento))  # espera exponencial: 0.5s, 1s, 2s
            if es_principal:
                self.circuito.falla()
            conmutada = True
        raise SinProveedoresError(ultimo_error)

    async def completar(self, sol: Solicitud) -> tuple[str, Uso]:
        """Versión sin streaming (regeneración de un fragmento, calificación)."""
        texto, uso = "", None
        async for ev in self.stream(sol):
            if ev.tipo == "chunk":
                texto += ev.texto
            elif ev.tipo == "reinicio":
                texto = ""
            elif ev.tipo == "fin":
                uso = ev.uso
        return texto, uso


adaptador = AdaptadorLLM()
