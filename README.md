# EducaGen

Aplicación web basada en LLMs para reducir el tiempo de elaboración de recursos educativos de calidad en universidades privadas de Lima.
Autoras: Andrea Cabanillas Gora y Beth Shantal Oneglio De Paz (UPC).

La implementación sigue el documento de arquitectura del Objetivo 2 y el Product Backlog (31 historias de usuario).

| Capa | Tecnología | Carpeta |
| --- | --- | --- |
| Interfaz web | Next.js 14 + React | `app/`, `components/`, `lib/` |
| API REST | FastAPI (Python 3.11+) | `backend/app/` |
| Base de datos | PostgreSQL (SQLite solo para pruebas rápidas) | `database/schema.sql` |
| IA | Gemini (principal) y Claude (respaldo), con reintentos e interruptor de circuito | `backend/app/services/llm/` |
| Streaming | Server-Sent Events | `backend/app/services/generacion.py`, `routers/asistente.py` |
| RAG | Banco de materiales modelo con búsqueda de texto completo | `backend/app/services/prompts.py`, `seed.py` |
| Exportación | PDF, Word, Excel, HTML y TXT con membrete | `backend/app/services/exportador.py` |

## Puesta en marcha

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    |  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

`backend/.env` ya trae la configuración local. Sin `DATABASE_URL` usa un archivo SQLite; para PostgreSQL:

```bash
docker compose up -d db          # PostgreSQL en localhost:5432
# y en backend/.env:
DATABASE_URL=postgresql://educagen:educagen@localhost:5432/educagen
```

Al iniciar, la API crea las tablas, carga los tipos de recurso, carreras y materiales modelo, y migra las cuentas de `data/usuarios.json` (las contraseñas siguen funcionando).

Documentación interactiva de la API: http://localhost:8000/docs

### 2. Frontend (Next.js)

```bash
npm install
npm run dev
```

Abre http://localhost:3000. Next.js reenvía las rutas `/api/*` a la API (ver `next.config.mjs`). `JWT_SECRET` debe ser igual en `.env.local` y en `backend/.env`.

### 3. Claves de IA

Sin claves la aplicación funciona en **modo demostración** (plantillas locales con el mismo flujo de streaming, validación y reintentos). Para usar los modelos reales agrega en `backend/.env`:

```
GEMINI_API_KEY=...
CLAUDE_API_KEY=...
```

Para mostrar la continuidad ante fallas en modo demostración:
- `LLM_SIMULAR_FALLA_PRINCIPAL=true`: Gemini falla 3 veces y responde Claude (HU0028, HU0029-1).
- `LLM_SIMULAR_FALLA_TOTAL=true`: fallan ambos y los datos quedan como borrador (HU0029-2).

## Pruebas

```bash
cd backend
pytest -q
```

`tests/test_servicios.py` cubre esquemas, conformidad, exportación y porcentaje editado; `tests/test_api.py` recorre el flujo completo (registro, generación, asistente, aprobación, exportación, historial, acceso denegado).

## Trazabilidad con el Product Backlog

| Historia | Dónde está |
| --- | --- |
| HU0001-HU0003 Cuenta, login, recuperación | `routers/auth.py`, `app/login`, `app/restablecer` |
| HU0004 Solo el dueño accede (403) | `deps.py` → `obtener_recurso_propio` |
| HU0005-HU0009 Generación en un paso | `app/(privado)/dashboard`, `routers/recursos.py` → `validar_parametros` |
| HU0010 Materiales modelo (RAG) | `services/prompts.py` → `recuperar_materiales` |
| HU0011 Regenerar selección (máx. 5) | Editor + `POST /api/recursos/{id}/regenerar` |
| HU0012-HU0014 Asistente, streaming, bibliografía APA | Editor + `routers/asistente.py` |
| HU0015-HU0016 Edición manual y autoguardado (con copia sin conexión) | `app/(privado)/editor/[id]` |
| HU0017-HU0020 Historial, búsqueda, duplicar, papelera 30 días | `app/(privado)/historial` |
| HU0021-HU0023 Exportar con formato y membrete | `services/exportador.py` |
| HU0024 Indicador de conformidad | `services/esquemas.py` → `verificar_conformidad` |
| HU0025, HU0027 Aprobación, % editado y tiempo activo | Editor + `/aprobacion`, `/aprobar` |
| HU0026, HU0032 Panel de calidad | `app/(privado)/calidad`, `routers/calidad.py` |
| HU0028-HU0029 Reintentos y respaldo | `services/llm/adaptador.py` |
| HU0034 Recurso completo (reintento correctivo) | `services/generacion.py` |

## Despliegue (Figura 2 del OB2)

- Frontend en Vercel con `API_URL` y `JWT_SECRET` como variables de entorno.
- API con `docker compose` en un servidor (AWS EC2) detrás de Nginx con HTTPS; PostgreSQL en Supabase o en el contenedor `db`.
- En producción usa `COOKIE_SEGURA=true` y un `JWT_SECRET` largo y aleatorio.
