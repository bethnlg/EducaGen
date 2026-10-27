"""API REST de EducaGen (FastAPI).

Ejecutar en desarrollo:  uvicorn app.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import config
from .routers import asistente, auth, calidad, recursos
from .seed import inicializar
from .services.llm import adaptador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    inicializar()  # crea tablas y datos iniciales si no existen
    ia = adaptador.descripcion()
    logging.getLogger("educagen").info("IA principal: %s | respaldo: %s", ia["principal"], ia["respaldo"])
    yield


app = FastAPI(title="EducaGen API", version="1.0.0", lifespan=ciclo_de_vida,
              description="API REST para generar, editar, validar y exportar recursos educativos con LLMs.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGENES,  # CORS restringido al dominio de la aplicación
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def error_validacion(_request: Request, exc: RequestValidationError):
    campos = [str(e["loc"][-1]) for e in exc.errors() if e.get("loc")]
    return JSONResponse(status_code=422, content={"detail": {"mensaje": "Revisa los datos enviados.", "campos": campos}})


app.include_router(auth.router)
app.include_router(recursos.router)
app.include_router(asistente.router)
app.include_router(calidad.router)


@app.get("/api/salud")
def salud():
    return {"ok": True, "ia": adaptador.descripcion()}
