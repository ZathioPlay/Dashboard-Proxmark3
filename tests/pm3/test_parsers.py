"""Tests de los parsers (funciones puras, con salidas de ejemplo)."""

from __future__ import annotations

import pytest

from pm3_dashboard.pm3.modelos import EstadoAntena, TipoTarjeta
from pm3_dashboard.pm3.parsers import (
    parsear_hf_search,
    parsear_hw_tune,
    parsear_hw_version,
    parsear_lf_search,
)
from tests.pm3.falsos import cargar_muestra

# ---------------------------------------------------------------- hw version


def test_hw_version_separa_cliente_y_firmware() -> None:
    info = parsear_hw_version(cargar_muestra("hw_version"))

    assert info is not None
    assert info.cliente.startswith("RRG/Iceman/master/v4.18994-48-gd2e0a3b4d 2024-07-21 15:02:39")
    assert info.firmware.startswith("RRG/Iceman/master/v4.18994-48-gd2e0a3b4d 2024-07-21 15:03:29")
    assert info.bootrom.startswith("RRG/Iceman/master/v4.18994")
    assert info.dispositivo == "RDV4"
    assert info.versiones_coinciden is True


def test_hw_version_detecta_versiones_distintas() -> None:
    info = parsear_hw_version(cargar_muestra("hw_version_distinta"))

    assert info is not None
    assert info.dispositivo == "PM3 GENERIC"
    assert info.versiones_coinciden is False


def test_hw_version_sin_conexion_solo_tiene_cliente() -> None:
    texto = " [ CLIENT ]\n  client: RRG/Iceman/master/v4.18994 2024-07-21\n[!!] cannot communicate"
    info = parsear_hw_version(texto)

    assert info is not None
    assert info.firmware == ""
    assert info.versiones_coinciden is None


def test_hw_version_sin_datos_devuelve_none() -> None:
    assert parsear_hw_version(cargar_muestra("sin_conexion")) is None


# ---------------------------------------------------------------- hw tune


def test_hw_tune_formato_actual_ok() -> None:
    medicion = parsear_hw_tune(cargar_muestra("hw_tune_ok"))

    assert medicion.lf.voltios == 44.28  # el de 125 kHz, no el óptimo
    assert medicion.lf.estado is EstadoAntena.OK
    assert medicion.hf.voltios == 31.40
    assert medicion.hf.estado is EstadoAntena.OK


def test_hw_tune_veredictos_marginal_e_inutilizable() -> None:
    medicion = parsear_hw_tune(cargar_muestra("hw_tune_marginal"))

    assert medicion.lf.voltios == 17.85
    assert medicion.lf.estado is EstadoAntena.MARGINAL
    assert medicion.hf.voltios == 2.71
    assert medicion.hf.estado is EstadoAntena.INUTILIZABLE


def test_hw_tune_sin_veredicto_usa_los_minimos() -> None:
    medicion = parsear_hw_tune(cargar_muestra("hw_tune_antiguo"))

    assert medicion.lf.voltios == 43.11
    assert medicion.lf.estado is EstadoAntena.OK  # >= 20 V
    assert medicion.hf.voltios == 12.40
    assert medicion.hf.estado is EstadoAntena.BAJA  # < 18 V


def test_hw_tune_sin_datos() -> None:
    medicion = parsear_hw_tune(cargar_muestra("sin_conexion"))

    assert medicion.lf.voltios is None
    assert medicion.lf.estado is EstadoAntena.SIN_DATOS
    assert medicion.hf.estado is EstadoAntena.SIN_DATOS


def test_hw_tune_ignora_colores_ansi() -> None:
    texto = cargar_muestra("hw_tune_ok").replace("( ok )", "( \x1b[32mok\x1b[0m )")

    assert parsear_hw_tune(texto).hf.estado is EstadoAntena.OK


# ---------------------------------------------------------------- hf search


@pytest.mark.parametrize(
    ("muestra", "uid", "atqa", "sak", "tipo"),
    [
        ("hf_search_1k", "5A 3E 7C 1B", "00 04", "08", TipoTarjeta.MIFARE_CLASSIC_1K),
        ("hf_search_4k", "9E 2B 44 C0", "00 02", "18", TipoTarjeta.MIFARE_CLASSIC_4K),
        ("hf_search_ntag", "04 68 95 71 FA 5C 64", "00 44", "00", TipoTarjeta.ULTRALIGHT_NTAG),
    ],
)
def test_hf_search_detecta_tarjeta(
    muestra: str, uid: str, atqa: str, sak: str, tipo: TipoTarjeta
) -> None:
    tarjeta = parsear_hf_search(cargar_muestra(muestra))

    assert tarjeta is not None
    assert tarjeta.uid == uid
    assert tarjeta.atqa == atqa
    assert tarjeta.sak == sak
    assert tarjeta.tipo is tipo


def test_hf_search_sin_tarjeta() -> None:
    assert parsear_hf_search(cargar_muestra("hf_search_vacio")) is None


def test_hf_search_uid_no_salta_de_linea() -> None:
    # Si la línea siguiente empieza por algo hexadecimal, no debe pegarse al UID.
    texto = "UID: 01 02 03 04\nAB CD otra linea\nATQA: 00 04"
    tarjeta = parsear_hf_search(texto)

    assert tarjeta is not None
    assert tarjeta.uid == "01 02 03 04"


def test_hf_search_tipo_desconocido_sin_atqa_ni_sak() -> None:
    tarjeta = parsear_hf_search("[+]  UID: de ad be ef\n")

    assert tarjeta is not None
    assert tarjeta.uid == "DE AD BE EF"
    assert tarjeta.atqa is None
    assert tarjeta.sak is None
    assert tarjeta.tipo is TipoTarjeta.ISO14443A


# ---------------------------------------------------------------- lf search


def test_lf_search_em410x_formato_actual() -> None:
    tarjeta = parsear_lf_search(cargar_muestra("lf_search_em410x"))

    assert tarjeta is not None
    assert tarjeta.id_em == "0F0368568B"


def test_lf_search_em410x_formato_antiguo() -> None:
    tarjeta = parsear_lf_search(cargar_muestra("lf_search_em410x_antiguo"))

    assert tarjeta is not None
    assert tarjeta.id_em == "1A2B3C4D5E"


def test_lf_search_sin_tarjeta() -> None:
    assert parsear_lf_search(cargar_muestra("lf_search_vacio")) is None
