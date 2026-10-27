"""Conexión a PostgreSQL mediante SQLAlchemy (I-03)."""
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import config

_url = config.DATABASE_URL
# Acepta URLs "postgres://" o "postgresql://" (Supabase) y usa el driver psycopg 3
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql+psycopg://", 1)
elif _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+psycopg://", 1)

_kwargs = {"pool_pre_ping": True}
if _url.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(_url, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# JSONB en PostgreSQL, JSON en otros motores
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def es_postgres() -> bool:
    return engine.dialect.name == "postgresql"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
