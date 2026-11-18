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
