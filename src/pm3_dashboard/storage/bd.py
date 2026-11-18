"""Conexión con la base de datos SQLite y aplicación de migraciones.

pywebview ejecuta cada llamada de la interfaz en un hilo distinto, así que se
abre una conexión por operación (las conexiones de sqlite3 no se comparten
entre hilos) con WAL y busy_timeout para que las escrituras simultáneas
esperen su turno en lugar de fallar con "database is locked".
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from pm3_dashboard.storage.migraciones import MIGRACIONES

BUSY_TIMEOUT_MS = 5000
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


class ErrorBaseDatos(Exception):
    """Error al abrir o migrar la base de datos (el mensaje se muestra al usuario)."""


def fecha_texto(momento: datetime | None = None) -> str:
    """Fecha y hora local en el formato que se guarda: 'YYYY-MM-DD HH:MM:SS'."""
    return (momento or datetime.now()).strftime(FORMATO_FECHA)


class BaseDatos:
    """Base de datos de la aplicación. Se migra sola la primera vez que se usa."""

    def __init__(self, ruta: Path, migraciones: Sequence[str] = MIGRACIONES) -> None:
        self.ruta = ruta
        self._migraciones = tuple(migraciones)
        self._mutex = threading.Lock()
        self._migrada = False

    @contextmanager
    def conexion(self) -> Iterator[sqlite3.Connection]:
        """Conexión para una operación: confirma al salir o deshace si hay error."""
        self._asegurar_migrada()
        con = self._abrir()
        try:
            with con:
                yield con
        finally:
            con.close()

    def version(self) -> int:
        con = self._abrir()
        try:
            return int(con.execute("PRAGMA user_version").fetchone()[0])
        finally:
            con.close()

    def migrar(self) -> int:
        """Aplica las migraciones pendientes y devuelve la versión final."""
        con = self._abrir()
        try:
            version = int(con.execute("PRAGMA user_version").fetchone()[0])
            if version > len(self._migraciones):
                raise ErrorBaseDatos(
                    f"La base de datos ({self.ruta}) es de una versión más nueva de la aplicación "
                    f"(esquema {version}). Actualiza PM3 Dashboard."
                )
            for numero in range(version, len(self._migraciones)):
                self._aplicar(con, numero + 1, self._migraciones[numero])
            return len(self._migraciones)
        finally:
            con.close()

    def _asegurar_migrada(self) -> None:
        with self._mutex:
            if not self._migrada:
                self.migrar()
                self._migrada = True

    def _abrir(self) -> sqlite3.Connection:
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(self.ruta, timeout=BUSY_TIMEOUT_MS / 1000)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys = ON")
            con.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            con.execute("PRAGMA journal_mode = WAL")
        except (OSError, sqlite3.Error) as exc:
            raise ErrorBaseDatos(f"No se pudo abrir la base de datos {self.ruta}: {exc}") from exc
        return con

    def _aplicar(self, con: sqlite3.Connection, version: int, script: str) -> None:
        """Una migración entera en una transacción: o se aplica toda o nada."""
        try:
            con.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {version};\nCOMMIT;")
        except sqlite3.Error as exc:
            if con.in_transaction:
                con.rollback()
            raise ErrorBaseDatos(f"Error al actualizar la base de datos a la versión {version}: {exc}") from exc
