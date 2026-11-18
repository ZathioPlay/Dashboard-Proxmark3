"""Tests de la detección de puerto (con detectores falsos)."""

from __future__ import annotations

from pm3_dashboard.pm3.puerto import detectar_puerto, puerto_presente


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


# ---------------------------------------------------------------- presencia


def test_presencia_con_auto_usa_la_deteccion() -> None:
    assert puerto_presente("auto", [lambda: "COM4"]) == "COM4"
    assert puerto_presente("auto", [lambda: None]) is None


def test_presencia_de_puerto_fijo_conectado() -> None:
    assert puerto_presente("com5", presentes=lambda: {"COM1", "COM5"}) == "com5"


def test_presencia_de_puerto_fijo_desconectado() -> None:
    assert puerto_presente("COM5", presentes=lambda: {"COM1"}) is None


def test_presencia_si_no_se_puede_saber_se_da_por_presente() -> None:
    assert puerto_presente("COM5", presentes=lambda: None) == "COM5"
    assert puerto_presente("COM5", presentes=_falla) == "COM5"
