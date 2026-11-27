-- =====================================================================
-- EducaGen - Esquema PostgreSQL (Figura 6 del OB2: diagrama físico)
-- La API crea estas tablas automáticamente al iniciar (SQLAlchemy).
-- Este script sirve como referencia o para crearlas manualmente:
--   psql -U educagen -d educagen -f database/schema.sql
-- =====================================================================

CREATE TABLE IF NOT EXISTS rol (
    id_rol        INTEGER PRIMARY KEY,
    nombre        VARCHAR(30)  NOT NULL UNIQUE,
    descripcion   VARCHAR(150)
);

CREATE TABLE IF NOT EXISTS usuario (
    id_usuario            SERIAL PRIMARY KEY,
    id_rol                INTEGER      NOT NULL REFERENCES rol(id_rol),
    nombres               VARCHAR(100) NOT NULL,
    apellidos             VARCHAR(100) NOT NULL DEFAULT '',
    correo_institucional  VARCHAR(150) NOT NULL UNIQUE,
    hash_contrasena       VARCHAR(255) NOT NULL,
    estado                VARCHAR(40)  NOT NULL DEFAULT 'activo',
    fecha_registro        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    ultimo_acceso         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS token_recuperacion (
    id_token          SERIAL PRIMARY KEY,
    id_usuario        INTEGER      NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    token_hash        VARCHAR(255) NOT NULL,
    fecha_expiracion  TIMESTAMPTZ  NOT NULL,
    usado             BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS token_verificacion (
    id_token          SERIAL PRIMARY KEY,
    id_usuario        INTEGER      NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    token_hash        VARCHAR(255) NOT NULL,
    fecha_expiracion  TIMESTAMPTZ  NOT NULL,
    usado             BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS carrera (
    id_carrera  SERIAL PRIMARY KEY,
    nombre      VARCHAR(120) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS curso (
    id_curso    SERIAL PRIMARY KEY,
    id_carrera  INTEGER REFERENCES carrera(id_carrera),
    codigo      VARCHAR(20),
    nombre      VARCHAR(150) NOT NULL,
    ciclo       SMALLINT
);

CREATE TABLE IF NOT EXISTS tipo_recurso (
    id_tipo_recurso     SERIAL PRIMARY KEY,
    clave               VARCHAR(20) NOT NULL UNIQUE,   -- silabo | rubrica | examen | caso
    nombre              VARCHAR(40) NOT NULL,
    esquema_estructura  JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS recurso_educativo (
    id_recurso          SERIAL PRIMARY KEY,
    id_usuario          INTEGER NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    id_curso            INTEGER NOT NULL REFERENCES curso(id_curso),
    id_tipo_recurso     INTEGER NOT NULL REFERENCES tipo_recurso(id_tipo_recurso),
    id_recurso_origen   INTEGER REFERENCES recurso_educativo(id_recurso) ON DELETE SET NULL,
    titulo              VARCHAR(200) NOT NULL,
    estado              VARCHAR(40)  NOT NULL DEFAULT 'borrador',  -- generando | borrador | pendiente | aprobado
    fecha_creacion      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ  NOT NULL DEFAULT now(),
    fecha_aprobacion    TIMESTAMPTZ,
    fecha_eliminacion   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_recurso_usuario ON recurso_educativo(id_usuario);

CREATE TABLE IF NOT EXISTS borrador (
    id_borrador     SERIAL PRIMARY KEY,
    id_recurso      INTEGER NOT NULL UNIQUE REFERENCES recurso_educativo(id_recurso) ON DELETE CASCADE,
    contenido       JSONB   NOT NULL DEFAULT '{}',
    fecha_guardado  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS version_recurso (
    id_version      SERIAL PRIMARY KEY,
    id_recurso      INTEGER NOT NULL REFERENCES recurso_educativo(id_recurso) ON DELETE CASCADE,
    numero_version  INTEGER NOT NULL,
    contenido       JSONB   NOT NULL DEFAULT '{}',
    origen          VARCHAR(20) NOT NULL,                  -- ia | docente
    fecha_creacion  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id_recurso, numero_version)
);

CREATE TABLE IF NOT EXISTS validacion_estructura (
    id_validacion        SERIAL PRIMARY KEY,
    id_version           INTEGER NOT NULL REFERENCES version_recurso(id_version) ON DELETE CASCADE,
    conforme             BOOLEAN NOT NULL,
    secciones_faltantes  JSONB   NOT NULL DEFAULT '[]',
    fecha_validacion     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS registro_edicion (
    id_registro            SERIAL PRIMARY KEY,
    id_recurso             INTEGER NOT NULL REFERENCES recurso_educativo(id_recurso) ON DELETE CASCADE,
    id_version_ia          INTEGER NOT NULL REFERENCES version_recurso(id_version),
    id_version_final       INTEGER NOT NULL REFERENCES version_recurso(id_version),
    porcentaje_modificado  NUMERIC(5,2) NOT NULL,
    fecha_registro         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tiempo_elaboracion (
    id_tiempo         SERIAL PRIMARY KEY,
    id_recurso        INTEGER NOT NULL UNIQUE REFERENCES recurso_educativo(id_recurso) ON DELETE CASCADE,
    fecha_inicio      TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_aprobacion  TIMESTAMPTZ,
    segundos_activos  INTEGER NOT NULL DEFAULT 0,
    numero_ediciones  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS archivo_exportado (
    id_archivo               SERIAL PRIMARY KEY,
    id_recurso               INTEGER NOT NULL REFERENCES recurso_educativo(id_recurso) ON DELETE CASCADE,
    id_version               INTEGER REFERENCES version_recurso(id_version) ON DELETE SET NULL,
    formato                  VARCHAR(10)  NOT NULL,
    incluye_membrete         BOOLEAN      NOT NULL DEFAULT FALSE,
    ruta_s3                  VARCHAR(500) NOT NULL,
    fecha_expiracion_enlace  TIMESTAMPTZ,
    fecha_exportacion        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS archivo_adjunto (
    id_archivo       VARCHAR(80) PRIMARY KEY,
    id_usuario       INTEGER NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    id_recurso       INTEGER REFERENCES recurso_educativo(id_recurso) ON DELETE CASCADE,
    nombre           VARCHAR(200) NOT NULL,
    tipo             VARCHAR(150) NOT NULL DEFAULT 'application/octet-stream',
    tamano           INTEGER NOT NULL,
    ruta             VARCHAR(500) NOT NULL,
    texto            TEXT NOT NULL DEFAULT '',
    texto_extraido   BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_carga      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_archivo_adjunto_usuario ON archivo_adjunto(id_usuario);
CREATE INDEX IF NOT EXISTS ix_archivo_adjunto_recurso ON archivo_adjunto(id_recurso);

CREATE TABLE IF NOT EXISTS material_modelo (
    id_material       SERIAL PRIMARY KEY,
    id_tipo_recurso   INTEGER NOT NULL REFERENCES tipo_recurso(id_tipo_recurso),
    id_carrera        INTEGER REFERENCES carrera(id_carrera),
    id_usuario_carga  INTEGER REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    ciclo             SMALLINT,
    titulo            VARCHAR(200) NOT NULL,
    contenido_texto   TEXT NOT NULL,
    ruta_archivo      VARCHAR(500),
    estado            VARCHAR(20) NOT NULL DEFAULT 'validado',
    fecha_carga       TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Búsqueda de texto completo para la recuperación de materiales modelo (RAG)
CREATE INDEX IF NOT EXISTS ix_material_fts ON material_modelo
    USING GIN (to_tsvector('spanish', titulo || ' ' || contenido_texto));

CREATE TABLE IF NOT EXISTS consulta_llm (
    id_consulta          SERIAL PRIMARY KEY,
    id_recurso           INTEGER REFERENCES recurso_educativo(id_recurso) ON DELETE SET NULL,
    id_usuario           INTEGER NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    proveedor            VARCHAR(40) NOT NULL,
    modelo               VARCHAR(120) NOT NULL,
    tipo_operacion       VARCHAR(40) NOT NULL,              -- generacion | asistente | regeneracion | calificacion
    tokens_entrada       INTEGER NOT NULL DEFAULT 0,
    tokens_salida        INTEGER NOT NULL DEFAULT 0,
    tiempo_respuesta_ms  INTEGER,
    numero_reintentos    SMALLINT NOT NULL DEFAULT 0,
    fue_conmutada        BOOLEAN  NOT NULL DEFAULT FALSE,
    estado               VARCHAR(20) NOT NULL,              -- exitosa | fallida | detenida
    fecha_consulta       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS consulta_material (
    id_consulta  INTEGER NOT NULL REFERENCES consulta_llm(id_consulta) ON DELETE CASCADE,
    id_material  INTEGER NOT NULL REFERENCES material_modelo(id_material) ON DELETE CASCADE,
    PRIMARY KEY (id_consulta, id_material)
);

CREATE TABLE IF NOT EXISTS alerta (
    id_alerta    SERIAL PRIMARY KEY,
    id_usuario   INTEGER NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    id_recurso   INTEGER REFERENCES recurso_educativo(id_recurso) ON DELETE CASCADE,
    id_consulta  INTEGER REFERENCES consulta_llm(id_consulta) ON DELETE SET NULL,
    tipo         VARCHAR(40)  NOT NULL,   -- seccion_faltante | material_faltante | consumo_inusual | diferencia_notas
    severidad    VARCHAR(10)  NOT NULL,   -- alta | media | baja
    titulo       VARCHAR(120) NOT NULL,
    descripcion  VARCHAR(300) NOT NULL,
    atendida     BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_alerta TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auditoria_calidad (
    id_auditoria            SERIAL PRIMARY KEY,
    id_recurso              INTEGER NOT NULL REFERENCES recurso_educativo(id_recurso) ON DELETE CASCADE,
    id_auditor              INTEGER NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    tasa_exactitud          NUMERIC(5,2),
    numero_inconsistencias  INTEGER NOT NULL DEFAULT 0,
    nota_ia                 NUMERIC(4,1),
    nota_final              NUMERIC(4,1),
    observaciones           TEXT,
    fecha_auditoria         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mensaje_asistente (
    id_mensaje   SERIAL PRIMARY KEY,
    id_recurso   INTEGER NOT NULL REFERENCES recurso_educativo(id_recurso) ON DELETE CASCADE,
    emisor       VARCHAR(20) NOT NULL,   -- docente | asistente
    contenido    TEXT NOT NULL,
    propuesta    JSONB,
    aplicado     BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_envio  TIMESTAMPTZ NOT NULL DEFAULT now()
);
