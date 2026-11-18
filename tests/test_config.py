"""Tests de la configuración (config.json en %APPDATA%)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pm3_dashboard import paths
from pm3_dashboard.config import (
    ConfigPm3,
    cargar_config,
    guardar_config,
    resolver_ruta_configurada,
    resolver_rutas_extra,
)


@pytest.fixture(autouse=True)
def sin_variables_pm3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PM3_BIN", raising=False)
    monkeypatch.delenv("PM3_PORT", raising=False)


def _escribir(appdata: Path, contenido: str) -> None:
    carpeta = appdata / "PM3-Dashboard"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "config.json").write_text(contenido, encoding="utf-8")


def test_sin_fichero_usa_valores_por_defecto(appdata_temporal: Path) -> None:
    assert cargar_config() == ConfigPm3(ruta_cliente="", puerto="auto", rutas_extra=[])


def test_json_corrupto_usa_valores_por_defecto(appdata_temporal: Path) -> None:
    _escribir(appdata_temporal, "{ esto no es json")

    assert cargar_config() == ConfigPm3()


def test_lee_el_fichero_e_ignora_valores_incorrectos(appdata_temporal: Path) -> None:
    _escribir(
        appdata_temporal,
        json.dumps({"ruta_cliente": "C:/pm3/proxmark3.exe", "puerto": 5, "rutas_extra": ["C:/dll", 3, ""]}),
    )

    config = cargar_config()

    assert config.ruta_cliente == "C:/pm3/proxmark3.exe"
    assert config.puerto == "auto"  # 5 no es texto
    assert config.rutas_extra == ["C:/dll"]


def test_las_variables_de_entorno_tienen_prioridad(
    appdata_temporal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _escribir(appdata_temporal, json.dumps({"ruta_cliente": "C:/a.exe", "puerto": "COM3"}))
    monkeypatch.setenv("PM3_BIN", "D:/b.exe")
    monkeypatch.setenv("PM3_PORT", "COM8")

    config = cargar_config()

    assert config.ruta_cliente == "D:/b.exe"
    assert config.puerto == "COM8"


def test_guardar_y_cargar(appdata_temporal: Path) -> None:
    original = ConfigPm3(ruta_cliente="C:/pm3/proxmark3.exe", puerto="COM4", rutas_extra=["C:/dll"])

    guardar_config(original)

    assert cargar_config() == original


def test_ruta_cliente_vacia_no_esta_configurada() -> None:
    # Sin ruta, el cliente se busca automáticamente (pm3/localizador.py).
    assert resolver_ruta_configurada(ConfigPm3()) is None
    assert resolver_ruta_configurada(ConfigPm3(ruta_cliente="   ")) is None


def test_rutas_relativas_desde_la_carpeta_de_la_app() -> None:
    config = ConfigPm3(ruta_cliente="otro/proxmark3.exe", rutas_extra=["dlls"])

    assert resolver_ruta_configurada(config) == (paths.carpeta_app() / "otro" / "proxmark3.exe").resolve()
    assert resolver_rutas_extra(config) == [(paths.carpeta_app() / "dlls").resolve()]


def test_ruta_configurada_absoluta(tmp_path: Path) -> None:
    ruta = tmp_path / "pm3" / "proxmark3.exe"

    assert resolver_ruta_configurada(ConfigPm3(ruta_cliente=str(ruta))) == ruta
