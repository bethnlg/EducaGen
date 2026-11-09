"""Clientes HTTP con streaming para Gemini (I-05) y Claude (I-06)."""
import json
from typing import AsyncIterator

import httpx

from ...config import config
from .base import Proveedor, ProveedorError, Solicitud, Uso, estimar_tokens


def _error_http(codigo: int, cuerpo: str, proveedor: str) -> ProveedorError:
    transitorio = codigo in (408, 409, 425, 429) or codigo >= 500
    return ProveedorError(f"{proveedor} respondió {codigo}: {cuerpo[:300]}", transitorio=transitorio)


async def _lineas_sse(respuesta: httpx.Response) -> AsyncIterator[str]:
    async for linea in respuesta.aiter_lines():
        linea = linea.strip()
        if linea.startswith("data:"):
            datos = linea[5:].strip()
            if datos and datos != "[DONE]":
                yield datos


class GeminiProveedor(Proveedor):
    nombre = "gemini"

    def __init__(self):
        self.modelo = config.GEMINI_MODEL

    def disponible(self) -> bool:
        return bool(config.GEMINI_API_KEY)

    async def stream(self, sol: Solicitud, uso: Uso) -> AsyncIterator[str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.modelo}:streamGenerateContent"
        cuerpo = {
            "systemInstruction": {"parts": [{"text": sol.sistema}]},
            "contents": [{"role": "user", "parts": [{"text": sol.prompt}]}],
            "generationConfig": {"temperature": sol.temperatura, "maxOutputTokens": sol.max_tokens},
        }
        if sol.json:
            cuerpo["generationConfig"]["responseMimeType"] = "application/json"
        uso.proveedor, uso.modelo = self.nombre, self.modelo
        texto_total = ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(config.LLM_TIMEOUT_SEG, connect=10)) as cliente:
                async with cliente.stream(
                    "POST", url, params={"alt": "sse"}, json=cuerpo,
                    headers={"x-goog-api-key": config.GEMINI_API_KEY},
                ) as r:
                    if r.status_code != 200:
                        raise _error_http(r.status_code, (await r.aread()).decode("utf-8", "ignore"), "Gemini")
                    async for datos in _lineas_sse(r):
                        try:
                            evento = json.loads(datos)
                        except json.JSONDecodeError:
                            continue
                        meta = evento.get("usageMetadata") or {}
                        uso.tokens_entrada = meta.get("promptTokenCount", uso.tokens_entrada)
                        uso.tokens_salida = meta.get("candidatesTokenCount", uso.tokens_salida)
                        for cand in evento.get("candidates") or []:
                            for parte in (cand.get("content") or {}).get("parts") or []:
                                if parte.get("text"):
                                    texto_total += parte["text"]
                                    yield parte["text"]
        except httpx.TimeoutException as e:
            raise ProveedorError(f"Gemini superó el tiempo de espera: {e}") from e
        except httpx.HTTPError as e:
            raise ProveedorError(f"Gemini no está disponible: {e}") from e
        if not texto_total:
            raise ProveedorError("Gemini devolvió una respuesta vacía.")
        uso.tokens_entrada = uso.tokens_entrada or estimar_tokens(sol.sistema + sol.prompt)
        uso.tokens_salida = uso.tokens_salida or estimar_tokens(texto_total)


class ClaudeProveedor(Proveedor):
    nombre = "claude"

    def __init__(self):
        self.modelo = config.CLAUDE_MODEL

    def disponible(self) -> bool:
        return bool(config.CLAUDE_API_KEY)

    async def stream(self, sol: Solicitud, uso: Uso) -> AsyncIterator[str]:
        sistema = sol.sistema
        if sol.json:
            sistema += "\nResponde únicamente con el objeto JSON, sin texto adicional ni bloques de código."
        cuerpo = {
            "model": self.modelo,
            "max_tokens": sol.max_tokens,
            "temperature": sol.temperatura,
            "system": sistema,
            "messages": [{"role": "user", "content": sol.prompt}],
            "stream": True,
        }
        cabeceras = {
            "x-api-key": config.CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        uso.proveedor, uso.modelo = self.nombre, self.modelo
        texto_total = ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(config.LLM_TIMEOUT_SEG, connect=10)) as cliente:
                async with cliente.stream("POST", "https://api.anthropic.com/v1/messages", json=cuerpo, headers=cabeceras) as r:
                    if r.status_code != 200:
                        raise _error_http(r.status_code, (await r.aread()).decode("utf-8", "ignore"), "Claude")
                    async for datos in _lineas_sse(r):
                        try:
                            evento = json.loads(datos)
                        except json.JSONDecodeError:
                            continue
                        tipo = evento.get("type")
                        if tipo == "message_start":
                            uso.tokens_entrada = ((evento.get("message") or {}).get("usage") or {}).get("input_tokens", 0)
                        elif tipo == "content_block_delta":
                            texto = (evento.get("delta") or {}).get("text")
                            if texto:
                                texto_total += texto
                                yield texto
                        elif tipo == "message_delta":
                            uso.tokens_salida = (evento.get("usage") or {}).get("output_tokens", uso.tokens_salida)
                        elif tipo == "error":
                            err = evento.get("error") or {}
                            raise ProveedorError(f"Claude: {err.get('message', 'error')}", transitorio=err.get("type") == "overloaded_error")
        except httpx.TimeoutException as e:
            raise ProveedorError(f"Claude superó el tiempo de espera: {e}") from e
        except httpx.HTTPError as e:
            raise ProveedorError(f"Claude no está disponible: {e}") from e
        if not texto_total:
            raise ProveedorError("Claude devolvió una respuesta vacía.")
        uso.tokens_salida = uso.tokens_salida or estimar_tokens(texto_total)

class LlamaProveedor(Proveedor):
    """Llama 3 mediante una API compatible con OpenAI (Groq en la nube u Ollama local)."""

    nombre = "llama"

    def __init__(self):
        self.modelo = config.LLAMA_MODEL
        self.url = config.LLAMA_URL

    def disponible(self) -> bool:
        return bool(config.LLAMA_API_KEY)

    async def stream(self, sol: Solicitud, uso: Uso) -> AsyncIterator[str]:
        sistema = sol.sistema
        if sol.json:
            sistema += "\nResponde únicamente con el objeto JSON, sin texto adicional ni bloques de código."
        cuerpo = {
            "model": self.modelo,
            "max_tokens": sol.max_tokens,
            "temperature": sol.temperatura,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": sol.prompt},
            ],
            "stream": True,
        }
        if sol.json:
            cuerpo["response_format"] = {"type": "json_object"}
        cabeceras = {
            "Authorization": f"Bearer {config.LLAMA_API_KEY}",
            "Content-Type": "application/json",
        }
        uso.proveedor, uso.modelo = self.nombre, self.modelo
        texto_total = ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(config.LLM_TIMEOUT_SEG, connect=10)) as cliente:
                async with cliente.stream("POST", self.url, json=cuerpo, headers=cabeceras) as r:
                    if r.status_code != 200:
                        raise _error_http(r.status_code, (await r.aread()).decode("utf-8", "ignore"), "Llama")
                    async for datos in _lineas_sse(r):
                        try:
                            evento = json.loads(datos)
                        except json.JSONDecodeError:
                            continue
                        for opcion in evento.get("choices") or []:
                            texto = (opcion.get("delta") or {}).get("content")
                            if texto:
                                texto_total += texto
                                yield texto
                        consumo = evento.get("usage") or (evento.get("x_groq") or {}).get("usage")
                        if consumo:
                            uso.tokens_entrada = consumo.get("prompt_tokens", uso.tokens_entrada)
                            uso.tokens_salida = consumo.get("completion_tokens", uso.tokens_salida)
        except httpx.TimeoutException as e:
            raise ProveedorError(f"Llama superó el tiempo de espera: {e}") from e
        except httpx.HTTPError as e:
            raise ProveedorError(f"Llama no está disponible: {e}") from e
        if not texto_total:
            raise ProveedorError("Llama devolvió una respuesta vacía.")
        uso.tokens_salida = uso.tokens_salida or estimar_tokens(texto_total)