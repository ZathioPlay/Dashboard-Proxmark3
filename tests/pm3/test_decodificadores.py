"""Tests de los decodificadores (ASCII, claves, bits de acceso y NDEF)."""

from __future__ import annotations

import pytest

from pm3_dashboard.pm3.decodificadores import (
    RegistroNdef,
    accesos_coherentes,
    accesos_de_trailer,
    ascii_de_hex,
    claves_de_trailer,
    decodificar_ndef,
)
from pm3_dashboard.pm3.parsers import parsear_hf_mfu_dump
from tests.pm3.falsos import cargar_muestra

# Trailer con la configuración de transporte: claves FF..FF y accesos FF 07 80.
TRAILER_TRANSPORTE = "FF FF FF FF FF FF FF 07 80 69 A0 A1 A2 A3 A4 A5"


# ---------------------------------------------------------------- ASCII


def test_ascii_bytes_imprimibles_y_no_imprimibles() -> None:
    # "Hola" + 0x00 0x01 + "!".
    assert ascii_de_hex("48 6F 6C 61 00 01 21") == "Hola..!"


def test_ascii_de_hex_vacio_o_invalido() -> None:
    assert ascii_de_hex("") == ""
    assert ascii_de_hex("ZZ") == ""


# ---------------------------------------------------------------- claves


def test_claves_del_trailer() -> None:
    clave_a, clave_b = claves_de_trailer(TRAILER_TRANSPORTE)

    assert clave_a == "FFFFFFFFFFFF"
    assert clave_b == "A0A1A2A3A4A5"


def test_claves_de_un_bloque_que_no_mide_16_bytes() -> None:
    assert claves_de_trailer("FF FF FF") == (None, None)


# ---------------------------------------------------------------- bits de acceso


def test_accesos_de_transporte() -> None:
    accesos = accesos_de_trailer(TRAILER_TRANSPORTE)

    assert accesos is not None
    assert len(accesos) == 4
    assert accesos[0] == "lectura y escritura con clave A o B"  # bloques de datos (0,0,0)
    assert "clave A o B" in accesos[0]
    assert accesos_coherentes(TRAILER_TRANSPORTE) is True


def test_accesos_solo_lectura() -> None:
    # Bloques de datos con (C1,C2,C3)=(0,1,0): solo lectura. c1=0 c2=F c3=0.
    # byte6=~c2<<4|~c1 = F0|0F=0x0F? inv_c1=F, inv_c2=0 -> byte6 = 0x0F; byte7=c1<<4|inv_c3 = 0x00|F=0x0F; byte8=c3<<4|c2=0x0F
    trailer = "A0 A1 A2 A3 A4 A5 0F 0F 0F 00 B0 B1 B2 B3 B4 B5"
    accesos = accesos_de_trailer(trailer)

    assert accesos is not None
    assert accesos[0] == "solo lectura con clave A o B"


def test_accesos_incoherentes_no_se_pueden_interpretar() -> None:
    # Bytes 6-8 que no cumplen la copia invertida.
    trailer = "FF FF FF FF FF FF 11 22 33 69 00 00 00 00 00 00"
    assert accesos_de_trailer(trailer) is None
    assert accesos_coherentes(trailer) is False


def test_accesos_de_un_trailer_no_leido() -> None:
    assert accesos_de_trailer("") is None


# ---------------------------------------------------------------- NDEF


def test_ndef_url() -> None:
    volcado = parsear_hf_mfu_dump(cargar_muestra("hf_mfu_ntag_url"))
    paginas = [b.datos for s in volcado.sectores for b in s.bloques]

    registros = decodificar_ndef(paginas)

    assert registros == [RegistroNdef(tipo="uri", contenido="https://example.com")]


def test_ndef_texto() -> None:
    # TLV 03 len=09; record D1 01 05 54('T'); payload: 02(lang len 2) 'en' 'Hi'
    paginas = [
        "00 00 00 00", "00 00 00 00", "00 00 00 00", "E1 10 12 00",
        "03 09 D1 01", "05 54 02 65", "6E 48 69 FE",
    ]
    registros = decodificar_ndef(paginas)

    assert registros == [RegistroNdef(tipo="texto", contenido="Hi")]


def test_sin_ndef_devuelve_lista_vacia() -> None:
    volcado = parsear_hf_mfu_dump(cargar_muestra("hf_mfu_dump"))
    paginas = [b.datos for s in volcado.sectores for b in s.bloques]

    # La muestra base no lleva un mensaje NDEF 0x03 completo decodificable a texto/URL.
    registros = decodificar_ndef(["00 00 00 00"] * 4 + ["00 00 00 FE"])
    assert registros == []
    assert isinstance(decodificar_ndef(paginas), list)
