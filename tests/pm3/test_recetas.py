"""Tests de las recetas: datos derivados y comandos (mismos comandos que el prototipo)."""

from __future__ import annotations

import pytest

from pm3_dashboard.pm3.modelos import Banda, TarjetaHF, TarjetaLF, TipoTarjeta
from pm3_dashboard.pm3.recetas import derivados, receta_hf, receta_lf, uid_con_espacios

FECHA = "2026-11-18"
UID = "5A 3E 7C 1B"


# ---------------------------------------------------------------- derivados


def test_derivados_mifare_classic_1k() -> None:
    d = derivados(TipoTarjeta.MIFARE_CLASSIC_1K, UID)

    assert d.frecuencia == "HF 13.56 MHz"
    assert d.seguridad == "Crypto-1 (Requiere autopwn / nested)"
    assert d.tarjeta_destino == "Magic Card Gen1a / Gen2"
    assert d.comando_clonado == "hf mf cload -f dump_5A3E7C1B.bin"
    assert d.comando_emulacion == "hf mf sim --1k -u 5A3E7C1B"


def test_derivados_mifare_classic_4k() -> None:
    d = derivados(TipoTarjeta.MIFARE_CLASSIC_4K, UID)

    assert d.comando_emulacion == "hf mf sim --4k -u 5A3E7C1B"
    assert d.seguridad == "Cifrado estándar"


def test_derivados_ultralight_ntag() -> None:
    d = derivados(TipoTarjeta.ULTRALIGHT_NTAG, "04 68 95 71 FA 5C 64")

    assert d.tarjeta_destino == "Magic Ultralight / NTAG21x"
    assert d.comando_clonado == "hf mfu restore -f dump_04689571FA5C64.bin"
    assert d.comando_emulacion == "hf mfu sim -t 7 -u 04689571FA5C64"


def test_derivados_iso14443a_generica() -> None:
    d = derivados(TipoTarjeta.ISO14443A, UID)

    assert d.frecuencia == "HF 13.56 MHz"
    assert d.comando_emulacion == "hf mf sim --1k -u 5A3E7C1B"


def test_derivados_em410x() -> None:
    d = derivados(TipoTarjeta.EM410X, "0F 03 68 56 8B")

    assert d.frecuencia == "LF 125 kHz"
    assert d.tarjeta_destino == "Chip T5577 (125 kHz)"
    assert d.seguridad == "Sin cifrado (Solo UID)"
    assert d.comando_clonado == "lf em 410x clone --id 0F0368568B"
    assert d.comando_emulacion == "lf em 410x sim --id 0F0368568B"


@pytest.mark.parametrize("uid", ["5a3e7c1b", "5A 3E 7C 1B", " 5a3e 7c1b "])
def test_derivados_acepta_uid_con_o_sin_espacios(uid: str) -> None:
    assert derivados(TipoTarjeta.MIFARE_CLASSIC_1K, uid).comando_emulacion == "hf mf sim --1k -u 5A3E7C1B"


@pytest.mark.parametrize("uid", ["0F0368568B; hw tune", "0F03 68 56 8B && rm", "", "ABC", "zz"])
def test_derivados_nunca_mete_algo_que_no_sea_hexadecimal_en_un_comando(uid: str) -> None:
    with pytest.raises(ValueError):
        derivados(TipoTarjeta.EM410X, uid)


def test_derivados_rechaza_tipos_desconocidos() -> None:
    with pytest.raises(ValueError):
        derivados("ISO14443-A (HF)", UID)  # texto antiguo de la fase 2  # type: ignore[arg-type]


def test_cada_tipo_tiene_su_banda() -> None:
    assert TipoTarjeta.EM410X.banda is Banda.LF
    assert TipoTarjeta.de_banda("lf") == {TipoTarjeta.EM410X}
    assert TipoTarjeta.MIFARE_CLASSIC_1K in TipoTarjeta.de_banda(Banda.HF)


def test_uid_con_espacios() -> None:
    assert uid_con_espacios("0f0368568b") == "0F 03 68 56 8B"


# ---------------------------------------------------------------- recetas de lectura


def test_receta_hf() -> None:
    tarjeta = receta_hf(
        TarjetaHF(uid=UID, atqa="00 04", sak="08", tipo=TipoTarjeta.MIFARE_CLASSIC_1K), "  salida  ", FECHA
    )

    assert tarjeta.banda is Banda.HF
    assert tarjeta.tipo is TipoTarjeta.MIFARE_CLASSIC_1K
    assert tarjeta.salida == "salida"
    assert tarjeta.fecha == FECHA
    assert tarjeta.derivados == derivados(TipoTarjeta.MIFARE_CLASSIC_1K, UID)


def test_receta_hf_sin_atqa_ni_sak_usa_valores_por_defecto() -> None:
    tarjeta = receta_hf(TarjetaHF(uid=UID, atqa=None, sak=None, tipo=TipoTarjeta.ISO14443A), "", FECHA)

    assert tarjeta.tipo == "ISO14443-A"
    assert tarjeta.atqa == "00 04"
    assert tarjeta.sak == "08"


def test_receta_em410x_usa_el_tipo_canonico() -> None:
    tarjeta = receta_lf(TarjetaLF(id_em="0F0368568B"), "", FECHA)

    assert tarjeta.banda is Banda.LF
    assert tarjeta.tipo is TipoTarjeta.EM410X
    assert tarjeta.tipo == "EM410x"  # el mismo texto que guarda la BD
    assert tarjeta.uid == "0F 03 68 56 8B"
    assert (tarjeta.atqa, tarjeta.sak) == ("", "")
    assert tarjeta.derivados.comando_clonado == "lf em 410x clone --id 0F0368568B"


# ---------------------------------------------------------------- nombre de archivo de clonado

from pm3_dashboard.pm3.recetas import nombre_archivo_volcado  # noqa: E402


def test_nombre_archivo_volcado_desde_uid_validado() -> None:
    assert nombre_archivo_volcado("5A 3E 7C 1B") == "dump_5A3E7C1B.bin"
    assert nombre_archivo_volcado("0f0368568b") == "dump_0F0368568B.bin"


@pytest.mark.parametrize("uid", ["../../evil", "5A3E/..", "5A 3E; rm", "", "zz", r"..\..\x"])
def test_nombre_archivo_volcado_rechaza_uid_manipulado(uid: str) -> None:
    # Nunca debe producir un nombre con separadores de ruta: el UID se valida como hex.
    with pytest.raises(ValueError):
        nombre_archivo_volcado(uid)


# ---------------------------------------------------------------- escritura de bloques

from pm3_dashboard.pm3.modelos import Tecnologia  # noqa: E402
from pm3_dashboard.pm3.recetas import (  # noqa: E402
    comando_escribir_bloque,
    comando_leer_bloque,
    es_trailer,
    texto_a_hex,
)

CLASSIC = Tecnologia.MIFARE_CLASSIC
ULTRA = Tecnologia.MIFARE_ULTRALIGHT


def test_comando_escribir_classic() -> None:
    cmd = comando_escribir_bloque(CLASSIC, 1, "00112233445566778899AABBCCDDEEFF")
    assert cmd == "hf mf wrbl --blk 1 -a -k FFFFFFFFFFFF -d 00112233445566778899AABBCCDDEEFF"


def test_comando_escribir_classic_clave_b() -> None:
    cmd = comando_escribir_bloque(CLASSIC, 5, "aa" * 16, clave="a0a1a2a3a4a5", usar_clave_b=True)
    assert cmd == "hf mf wrbl --blk 5 -b -k A0A1A2A3A4A5 -d " + "AA" * 16


def test_comando_escribir_ultralight() -> None:
    assert comando_escribir_bloque(ULTRA, 4, "04 68 95 71") == "hf mfu wrbl -b 4 -d 04689571"


def test_comando_leer_bloque() -> None:
    assert comando_leer_bloque(CLASSIC, 2) == "hf mf rdbl --blk 2 -a -k FFFFFFFFFFFF"
    assert comando_leer_bloque(ULTRA, 4) == "hf mfu rdbl -b 4"


@pytest.mark.parametrize(
    ("tec", "datos"),
    [
        (CLASSIC, "00112233"),                 # muy corto
        (CLASSIC, "00" * 17),                  # muy largo
        (CLASSIC, "ZZ" + "00" * 15),           # no hexadecimal
        (ULTRA, "0011223344"),                 # 5 bytes en vez de 4
        (ULTRA, "GG001122"),                   # no hexadecimal
    ],
)
def test_escribir_rechaza_datos_invalidos(tec: Tecnologia, datos: str) -> None:
    with pytest.raises(ValueError):
        comando_escribir_bloque(tec, 1, datos)


def test_escribir_rechaza_clave_invalida() -> None:
    with pytest.raises(ValueError):
        comando_escribir_bloque(CLASSIC, 1, "00" * 16, clave="123")


def test_escribir_rechaza_indice_negativo() -> None:
    with pytest.raises(ValueError):
        comando_escribir_bloque(CLASSIC, -1, "00" * 16)


@pytest.mark.parametrize(
    ("indice", "tipo", "esperado"),
    [
        (3, TipoTarjeta.MIFARE_CLASSIC_1K, True),
        (7, TipoTarjeta.MIFARE_CLASSIC_1K, True),
        (63, TipoTarjeta.MIFARE_CLASSIC_1K, True),
        (4, TipoTarjeta.MIFARE_CLASSIC_1K, False),
        (0, TipoTarjeta.MIFARE_CLASSIC_1K, False),
        (3, TipoTarjeta.MIFARE_CLASSIC_4K, True),
        (143, TipoTarjeta.MIFARE_CLASSIC_4K, True),   # trailer de sector grande de 4K
        (159, TipoTarjeta.MIFARE_CLASSIC_4K, True),
        (255, TipoTarjeta.MIFARE_CLASSIC_4K, True),
        (140, TipoTarjeta.MIFARE_CLASSIC_4K, False),
        (4, TipoTarjeta.ULTRALIGHT_NTAG, False),      # Ultralight no tiene trailers
    ],
)
def test_es_trailer_1k_y_4k(indice: int, tipo: TipoTarjeta, esperado: bool) -> None:
    assert es_trailer(indice, tipo) is esperado


def test_texto_a_hex_rellena_y_trunca() -> None:
    assert texto_a_hex("Hola", 16) == "486F6C61" + "00" * 12
    assert texto_a_hex("Hola", 4) == "486F6C61"
    assert texto_a_hex("larguísimo", 4) == "6C617267"  # truncado a 4 bytes
