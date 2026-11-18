"""Tests de pm3_dashboard.paths."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pm3_dashboard import paths


def test_carpeta_ui_en_desarrollo_contiene_index() -> None:
    assert not paths.esta_empaquetada()
    assert paths.carpeta_ui().is_dir()
    assert paths.ruta_index().is_file()
    assert paths.ruta_index().name == "index.html"


def test_carpeta_ui_empaquetada_usa_meipass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert paths.esta_empaquetada()
    assert paths.carpeta_ui() == tmp_path / "pm3_dashboard" / "ui"


def test_carpeta_datos_se_crea_en_appdata(appdata_temporal: Path) -> None:
    carpeta = paths.carpeta_datos()

    assert carpeta == appdata_temporal / "PM3-Dashboard"
    assert carpeta.is_dir()


def test_rutas_de_bd_y_config_estan_en_carpeta_datos(appdata_temporal: Path) -> None:
    carpeta = appdata_temporal / "PM3-Dashboard"

    assert paths.ruta_bd() == carpeta / "pm3.db"
    assert paths.ruta_config() == carpeta / "config.json"
