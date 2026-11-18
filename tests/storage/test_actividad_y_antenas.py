"""Tests del registro de actividad y del historial de mediciones de antenas."""

from __future__ import annotations

from datetime import datetime

import pytest

from pm3_dashboard.pm3.modelos import EstadoAntena, MedicionAntena, MedicionAntenas
from pm3_dashboard.storage import BaseDatos, actividad, antenas
from pm3_dashboard.storage.actividad import TipoActividad


def test_actividad_mas_reciente_primero_y_con_limite(bd: BaseDatos) -> None:
    for hora in range(10):
        actividad.registrar(bd, TipoActividad.LECTURA, f"evento {hora}", datetime(2026, 11, 18, hora))

    eventos = actividad.ultimas(bd, limite=3)

    assert [e.descripcion for e in eventos] == ["evento 9", "evento 8", "evento 7"]
    assert eventos[0].fecha == "2026-11-18 09:00:00"
    assert eventos[0].tipo == "lectura"


def test_actividad_vacia(bd: BaseDatos) -> None:
    assert actividad.ultimas(bd) == []


def test_actividad_rechaza_tipos_desconocidos(bd: BaseDatos) -> None:
    with pytest.raises(ValueError):
        actividad.registrar(bd, "inventado", "x")
    assert actividad.ultimas(bd) == []


def test_sin_mediciones(bd: BaseDatos) -> None:
    assert antenas.ultima_medicion(bd) is None


def test_guardar_y_leer_la_ultima_medicion(bd: BaseDatos) -> None:
    antigua = MedicionAntenas(
        lf=MedicionAntena(30.0, EstadoAntena.OK), hf=MedicionAntena(20.0, EstadoAntena.OK)
    )
    nueva = MedicionAntenas(
        lf=MedicionAntena(17.85, EstadoAntena.MARGINAL), hf=MedicionAntena(None, EstadoAntena.SIN_DATOS)
    )
    antenas.guardar_medicion(bd, antigua, datetime(2026, 11, 17, 10))
    antenas.guardar_medicion(bd, nueva, datetime(2026, 11, 18, 10))

    ultima = antenas.ultima_medicion(bd)

    assert ultima is not None
    assert ultima.fecha == "2026-11-18 10:00:00"
    assert ultima.medicion == nueva


def test_historial_de_antenas(bd: BaseDatos) -> None:
    for h in range(5):
        m = MedicionAntenas(lf=MedicionAntena(30.0 + h, EstadoAntena.OK), hf=MedicionAntena(20.0, EstadoAntena.OK))
        antenas.guardar_medicion(bd, m, datetime(2026, 11, 18, 10 + h))

    historial = antenas.historial(bd, limite=3)

    assert [g.fecha for g in historial] == ["2026-11-18 14:00:00", "2026-11-18 13:00:00", "2026-11-18 12:00:00"]
    assert historial[0].medicion.lf.voltios == 34.0
    assert antenas.historial(bd) == antenas.historial(bd, 10)  # por defecto 10


def test_historial_vacio(bd: BaseDatos) -> None:
    assert antenas.historial(bd) == []
