"""Registro de actividad (lo que se muestra en "Actividad reciente")."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pm3_dashboard.storage.bd import BaseDatos, fecha_texto

MAX_DESCRIPCION = 500


class TipoActividad(StrEnum):
    # Se definen aquí (no con CHECK en SQL) para poder añadir tipos sin migración.
    LECTURA = "lectura"
    ANTENAS = "antenas"
    GUARDADO = "guardado"
    EMULACION = "emulacion"
    CONEXION = "conexion"
    CLONADO = "clonado"
    ESCRITURA = "escritura"
    BORRADO = "borrado"
    IMPORTACION = "importacion"
    EXPORTACION = "exportacion"


@dataclass(frozen=True)
class Evento:
    id: int
    fecha: str
    tipo: str
    descripcion: str


def registrar(
    bd: BaseDatos, tipo: TipoActividad | str, descripcion: str, momento: datetime | None = None
) -> int:
    """Añade un evento. Lanza ValueError si el tipo no existe."""
    tipo = TipoActividad(tipo)
    descripcion = descripcion.strip()[:MAX_DESCRIPCION]
    with bd.conexion() as con:
        cursor = con.execute(
            "INSERT INTO actividad (fecha, tipo, descripcion) VALUES (?, ?, ?)",
            (fecha_texto(momento), tipo.value, descripcion),
        )
        return int(cursor.lastrowid or 0)


def ultimas(bd: BaseDatos, limite: int = 8) -> list[Evento]:
    """Eventos más recientes primero."""
    with bd.conexion() as con:
        filas = con.execute(
            "SELECT id, fecha, tipo, descripcion FROM actividad ORDER BY fecha DESC, id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [Evento(**dict(fila)) for fila in filas]
