"""Migraciones del esquema de la base de datos.

Cada elemento de MIGRACIONES es el script SQL que lleva la base de datos de
la versión N a la N+1 (la versión se guarda en PRAGMA user_version). Para
cambiar el esquema se AÑADE una migración al final; nunca se modifican las
que ya existen, porque ya se han aplicado en los PCs de los usuarios.
"""

from __future__ import annotations

# v1: tarjetas, actividad y mediciones de antenas.
# A diferencia del prototipo (rfid-clone/database/schema.sql):
# - No hay usuarios ni sesiones (app local de un solo usuario).
# - No se guardan comandos de clonado/emulación ni datos derivados (tarjeta
#   destino, seguridad, frecuencia): se regeneran con pm3/recetas.py.
_V1 = """
CREATE TABLE tarjetas (
    id      INTEGER PRIMARY KEY,
    nombre  TEXT NOT NULL,
    notas   TEXT NOT NULL DEFAULT '',
    fecha   TEXT NOT NULL,
    banda   TEXT NOT NULL CHECK (banda IN ('hf', 'lf')),
    tipo    TEXT NOT NULL,
    uid     TEXT NOT NULL,
    atqa    TEXT NOT NULL DEFAULT '',
    sak     TEXT NOT NULL DEFAULT '',
    salida  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_tarjetas_banda ON tarjetas (banda);

CREATE TABLE actividad (
    id           INTEGER PRIMARY KEY,
    fecha        TEXT NOT NULL,
    tipo         TEXT NOT NULL,
    descripcion  TEXT NOT NULL
);
CREATE INDEX idx_actividad_fecha ON actividad (fecha);

CREATE TABLE mediciones_antenas (
    id          INTEGER PRIMARY KEY,
    fecha       TEXT NOT NULL,
    lf_voltios  REAL,
    lf_estado   TEXT NOT NULL,
    hf_voltios  REAL,
    hf_estado   TEXT NOT NULL
);
CREATE INDEX idx_mediciones_fecha ON mediciones_antenas (fecha);
"""

# v2: volcados de memoria (leer bloques HF). Un volcado es un dato LEÍDO de la
# tarjeta (bloques en hexadecimal), nunca un comando. Se borra con su tarjeta.
_V2 = """
CREATE TABLE volcados (
    id              INTEGER PRIMARY KEY,
    tarjeta_id      INTEGER NOT NULL REFERENCES tarjetas(id) ON DELETE CASCADE,
    fecha           TEXT NOT NULL,
    tecnologia      TEXT NOT NULL,
    bloques_leidos  INTEGER NOT NULL,
    total_bloques   INTEGER NOT NULL,
    completo        INTEGER NOT NULL,
    salida          TEXT NOT NULL DEFAULT '',
    datos_json      TEXT NOT NULL
);
CREATE INDEX idx_volcados_tarjeta ON volcados (tarjeta_id);
"""

MIGRACIONES: tuple[str, ...] = (_V1, _V2)
