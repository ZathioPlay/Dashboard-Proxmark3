"""Tests de la conexión y las migraciones."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from pm3_dashboard.storage import BaseDatos, ErrorBaseDatos
from pm3_dashboard.storage import actividad
from pm3_dashboard.storage.bd import BUSY_TIMEOUT_MS
from pm3_dashboard.storage.migraciones import MIGRACIONES

M1 = "CREATE TABLE a (x INTEGER);"
M2 = "CREATE TABLE b (y INTEGER); INSERT INTO a (x) VALUES (2);"
M_ROTA = "CREATE TABLE c (z INTEGER); INSERT INTO tabla_que_no_existe VALUES (1);"


def _tablas(ruta: Path) -> set[str]:
    con = sqlite3.connect(ruta)
    try:
        return {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        con.close()


def test_bd_nueva_queda_en_la_ultima_version(bd: BaseDatos) -> None:
    assert bd.migrar() == len(MIGRACIONES)
    assert bd.version() == len(MIGRACIONES)
    assert {"tarjetas", "actividad", "mediciones_antenas"} <= _tablas(bd.ruta)


def test_no_se_guardan_comandos_de_clonado_ni_emulacion(bd: BaseDatos) -> None:
    bd.migrar()
    with bd.conexion() as con:
        columnas = {fila["name"] for fila in con.execute("PRAGMA table_info(tarjetas)")}

    assert not {"clone_cmd", "sim_cmd", "comando_clonado", "comando_emulacion"} & columnas


def test_migrar_dos_veces_no_repite_nada(bd: BaseDatos) -> None:
    bd.migrar()
    assert bd.migrar() == len(MIGRACIONES)  # si repitiera, CREATE TABLE fallaría


def test_se_migra_sola_al_usarla(bd: BaseDatos) -> None:
    with bd.conexion() as con:
        con.execute("SELECT COUNT(*) FROM tarjetas")
    assert bd.version() == len(MIGRACIONES)


def test_actualiza_una_bd_antigua_conservando_datos(tmp_path: Path) -> None:
    ruta = tmp_path / "pm3.db"
    with BaseDatos(ruta, migraciones=[M1]).conexion() as con:
        con.execute("INSERT INTO a (x) VALUES (1)")

    nueva = BaseDatos(ruta, migraciones=[M1, M2])
    assert nueva.migrar() == 2
    with nueva.conexion() as con:
        valores = [fila["x"] for fila in con.execute("SELECT x FROM a ORDER BY x")]
    assert valores == [1, 2]
    assert "b" in _tablas(ruta)


def test_una_migracion_que_falla_no_deja_la_bd_a_medias(tmp_path: Path) -> None:
    ruta = tmp_path / "pm3.db"
    BaseDatos(ruta, migraciones=[M1]).migrar()

    with pytest.raises(ErrorBaseDatos, match="versión 2"):
        BaseDatos(ruta, migraciones=[M1, M_ROTA]).migrar()

    assert BaseDatos(ruta, migraciones=[M1]).version() == 1
    assert "c" not in _tablas(ruta)  # la parte que sí funcionó se deshizo


def test_bd_de_una_version_mas_nueva(tmp_path: Path) -> None:
    ruta = tmp_path / "pm3.db"
    BaseDatos(ruta, migraciones=[M1, M2]).migrar()

    with pytest.raises(ErrorBaseDatos, match="más nueva"):
        BaseDatos(ruta, migraciones=[M1]).migrar()


def test_wal_y_busy_timeout(bd: BaseDatos) -> None:
    with bd.conexion() as con:
        assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert con.execute("PRAGMA busy_timeout").fetchone()[0] == BUSY_TIMEOUT_MS
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_error_si_no_se_puede_abrir(tmp_path: Path) -> None:
    carpeta = tmp_path / "es_una_carpeta.db"
    carpeta.mkdir()

    with pytest.raises(ErrorBaseDatos, match="No se pudo abrir"):
        BaseDatos(carpeta).migrar()


def test_escrituras_simultaneas_desde_varios_hilos(bd: BaseDatos) -> None:
    """Como pywebview: cada llamada en un hilo. No debe fallar con 'database is locked'."""
    hilos_n, escrituras_n = 8, 25
    salida = threading.Barrier(hilos_n)
    errores: list[BaseException] = []

    def escribir(numero: int) -> None:
        try:
            salida.wait()  # que todos empiecen a la vez
            for i in range(escrituras_n):
                actividad.registrar(bd, "conexion", f"hilo {numero} escritura {i}")
        except BaseException as exc:  # se comprueba abajo que no haya ninguno
            errores.append(exc)

    hilos = [threading.Thread(target=escribir, args=(n,)) for n in range(hilos_n)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(30)

    assert errores == []
    with bd.conexion() as con:
        assert con.execute("SELECT COUNT(*) FROM actividad").fetchone()[0] == hilos_n * escrituras_n
