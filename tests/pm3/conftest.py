"""Fixtures para probar pm3/ con un cliente falso."""

from __future__ import annotations

from pathlib import Path

import pytest

from pm3_dashboard.config import ConfigPm3
from pm3_dashboard.pm3.cliente import ClientePm3
from pm3_dashboard.pm3.proxmark import Proxmark3
from tests.pm3.falsos import LanzadorFalso


@pytest.fixture
def ejecutable(tmp_path: Path) -> Path:
    """Fichero vacío que hace de proxmark3.exe (nunca se ejecuta)."""
    ruta = tmp_path / "cliente" / "proxmark3.exe"
    ruta.parent.mkdir()
    ruta.touch()
    return ruta


@pytest.fixture
def config(ejecutable: Path) -> ConfigPm3:
    return ConfigPm3(ruta_cliente=str(ejecutable), puerto="COM5")


@pytest.fixture
def lanzador() -> LanzadorFalso:
    return LanzadorFalso()


@pytest.fixture
def cliente(config: ConfigPm3, lanzador: LanzadorFalso, tmp_path: Path) -> ClientePm3:
    return ClientePm3(cargar=lambda: config, lanzador=lanzador, carpeta_trabajo=tmp_path / "dumps")


@pytest.fixture
def proxmark(cliente: ClientePm3) -> Proxmark3:
    return Proxmark3(cliente=cliente, hoy=lambda: "2026-11-18", espera_emulacion=0)
