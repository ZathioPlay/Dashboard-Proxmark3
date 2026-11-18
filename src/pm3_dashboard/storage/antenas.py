"""Historial de mediciones de antenas (hw tune)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pm3_dashboard.pm3.modelos import EstadoAntena, MedicionAntena, MedicionAntenas
from pm3_dashboard.storage.bd import BaseDatos, fecha_texto


@dataclass(frozen=True)
class MedicionGuardada:
    id: int
    fecha: str
    medicion: MedicionAntenas


def guardar_medicion(bd: BaseDatos, medicion: MedicionAntenas, momento: datetime | None = None) -> MedicionGuardada:
    fecha = fecha_texto(momento)
    with bd.conexion() as con:
        cursor = con.execute(
            """INSERT INTO mediciones_antenas (fecha, lf_voltios, lf_estado, hf_voltios, hf_estado)
               VALUES (?, ?, ?, ?, ?)""",
            (
                fecha,
                medicion.lf.voltios,
                medicion.lf.estado.value,
                medicion.hf.voltios,
                medicion.hf.estado.value,
            ),
        )
        return MedicionGuardada(id=int(cursor.lastrowid or 0), fecha=fecha, medicion=medicion)


def _estado(texto: str) -> EstadoAntena:
    try:
        return EstadoAntena(texto)
    except ValueError:
        return EstadoAntena.SIN_DATOS


def _desde_fila(fila) -> MedicionGuardada:  # noqa: ANN001 (sqlite3.Row)
    return MedicionGuardada(
        id=fila["id"],
        fecha=fila["fecha"],
        medicion=MedicionAntenas(
            lf=MedicionAntena(voltios=fila["lf_voltios"], estado=_estado(fila["lf_estado"])),
            hf=MedicionAntena(voltios=fila["hf_voltios"], estado=_estado(fila["hf_estado"])),
        ),
    )


def ultima_medicion(bd: BaseDatos) -> MedicionGuardada | None:
    with bd.conexion() as con:
        fila = con.execute(
            "SELECT * FROM mediciones_antenas ORDER BY fecha DESC, id DESC LIMIT 1"
        ).fetchone()
    return _desde_fila(fila) if fila else None


def historial(bd: BaseDatos, limite: int = 10) -> list[MedicionGuardada]:
    """Mediciones guardadas, de la más reciente a la más antigua."""
    with bd.conexion() as con:
        filas = con.execute(
            "SELECT * FROM mediciones_antenas ORDER BY fecha DESC, id DESC LIMIT ?", (limite,)
        ).fetchall()
    return [_desde_fila(fila) for fila in filas]
