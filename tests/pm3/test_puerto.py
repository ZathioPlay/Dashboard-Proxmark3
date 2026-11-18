"""Tests de la detección de puerto (con detectores falsos)."""

from __future__ import annotations

from pm3_dashboard.pm3.puerto import detectar_puerto


def _falla() -> str | None:
    raise RuntimeError("detector roto")


def test_puerto_fijo_se_usa_sin_detectar() -> None:
    llamado = []
    assert detectar_puerto("COM7", [lambda: llamado.append(1) or "COM3"]) == "COM7"
    assert llamado == []


def test_auto_usa_el_primer_detector_que_encuentra() -> None:
    assert detectar_puerto("auto", [lambda: None, lambda: "COM4", lambda: "COM9"]) == "COM4"


def test_auto_sin_mayusculas_ni_valor() -> None:
    assert detectar_puerto(" AUTO ", [lambda: "COM4"]) == "COM4"
    assert detectar_puerto("", [lambda: "COM4"]) == "COM4"
    assert detectar_puerto(None, [lambda: "COM4"]) == "COM4"


def test_auto_sin_proxmark_devuelve_none() -> None:
    assert detectar_puerto("auto", [lambda: None]) is None


def test_un_detector_que_falla_no_impide_probar_el_siguiente() -> None:
    assert detectar_puerto("auto", [_falla, lambda: "COM6"]) == "COM6"
