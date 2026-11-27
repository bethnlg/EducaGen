"""Configuración leída desde variables de entorno (RNF-02: sin secretos en el código)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:  # python-dotenv es opcional
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass


def _bool(nombre: str, defecto: bool = False) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


class Config:
    # Base de datos (PostgreSQL en producción; SQLite solo como respaldo local)
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'educagen.db'}")

    # Seguridad
    JWT_SECRET: str = os.getenv("JWT_SECRET", "clave-temporal-solo-para-desarrollo-123456")
    JWT_HORAS: int = int(os.getenv("JWT_HORAS", "8"))
    COOKIE_SEGURA: bool = _bool("COOKIE_SEGURA", False)
    CORS_ORIGENES: list[str] = [o.strip() for o in os.getenv("CORS_ORIGENES", "http://localhost:3000").split(",") if o.strip()]
    APP_URL: str = os.getenv("APP_URL", "http://localhost:3000")

    # Correo (Webhook HTTPS puerto 443 para Render/HF Spaces, Resend o SMTP con TLS)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USUARIO: str = os.getenv("SMTP_USUARIO", os.getenv("GMAIL_USER", ""))
    SMTP_CONTRASENA: str = os.getenv("SMTP_CONTRASENA", os.getenv("GMAIL_APP_PASSWORD", ""))
    CORREO_WEBHOOK_URL: str = os.getenv("CORREO_WEBHOOK_URL", "")
    CORREO_WEBHOOK_SECRET: str = os.getenv("CORREO_WEBHOOK_SECRET", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    CORREO_DESDE: str = os.getenv("CORREO_DESDE", "")
    REQUERIR_VERIFICACION_CORREO: bool = _bool("REQUERIR_VERIFICACION_CORREO", True)

    # Cuenta de demostración inicial (idempotente en seed.py)
    CREAR_USUARIO_DEMO: bool = _bool("CREAR_USUARIO_DEMO", True)
    DEMO_CORREO: str = os.getenv("DEMO_CORREO", "demo@universidad.edu.pe")
    DEMO_CONTRASENA: str = os.getenv("DEMO_CONTRASENA", "EducaGenDemo2026!")

    # Proveedores de LLM (RT-06): Groq/Llama, Gemini y Claude
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
    LLAMA_API_KEY: str = os.getenv("LLAMA_API_KEY", os.getenv("GROQ_API_KEY", ""))
    LLAMA_MODEL: str = os.getenv("LLAMA_MODEL", "openai/gpt-oss-120b")
    LLAMA_URL: str = os.getenv("LLAMA_URL", "https://api.groq.com/openai/v1/chat/completions")
    # "auto": usa las claves disponibles; "demo": generador local sin IA externa
    LLM_MODO: str = os.getenv("LLM_MODO", "auto").lower()
    LLM_TIMEOUT_SEG: float = float(os.getenv("LLM_TIMEOUT_SEG", "60"))
    LLM_REINTENTOS: int = int(os.getenv("LLM_REINTENTOS", "3"))
    LLM_SIMULAR_FALLA_PRINCIPAL: bool = _bool("LLM_SIMULAR_FALLA_PRINCIPAL", False)
    LLM_SIMULAR_FALLA_TOTAL: bool = _bool("LLM_SIMULAR_FALLA_TOTAL", False)
    CIRCUITO_FALLAS: int = int(os.getenv("CIRCUITO_FALLAS", "3"))
    CIRCUITO_ESPERA_SEG: int = int(os.getenv("CIRCUITO_ESPERA_SEG", "60"))
    # HU0032-2: consumo inusual de tokens
    MAX_TOKENS_SALIDA: int = int(os.getenv("MAX_TOKENS_SALIDA", "12000"))

    # Reglas de negocio
    MAX_RECURSOS: int = int(os.getenv("MAX_RECURSOS", "200"))
    MAX_PREGUNTAS: int = 20
    MAX_REGENERACIONES: int = 5
    DIAS_PAPELERA: int = 30

    # Exportación y membrete
    STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage" / "exports")))
    MAX_ARCHIVO_ADJUNTO_BYTES: int = int(os.getenv("MAX_ARCHIVO_ADJUNTO_BYTES", str(10 * 1024 * 1024)))
    MAX_ARCHIVOS_ADJUNTOS: int = int(os.getenv("MAX_ARCHIVOS_ADJUNTOS", "5"))
    MAX_TEXTO_ADJUNTO: int = int(os.getenv("MAX_TEXTO_ADJUNTO", "60000"))
    MAX_ALMACEN_ADJUNTOS_USUARIO: int = int(os.getenv("MAX_ALMACEN_ADJUNTOS_USUARIO", str(50 * 1024 * 1024)))
    UNIVERSIDAD_NOMBRE: str = os.getenv("UNIVERSIDAD_NOMBRE", "Universidad Peruana de Ciencias Aplicadas")
    MEMBRETE_LOGO: Path = Path(os.getenv("MEMBRETE_LOGO", str(BASE_DIR / "assets" / "membrete.png")))
    HORAS_ENLACE_DESCARGA: int = 24


config = Config()
