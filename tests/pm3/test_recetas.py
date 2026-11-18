"""Tests de las recetas de clonado y emulación (mismos comandos que el prototipo)."""

from __future__ import annotations

from pm3_dashboard.pm3.modelos import Banda, FamiliaHF, TarjetaHF, TarjetaLF
from pm3_dashboard.pm3.recetas import receta_hf, receta_lf

FECHA = "2026-11-18"


def _hf(familia: FamiliaHF, atqa: str | None = "00 04", sak: str | None = "08") -> TarjetaHF:
    return TarjetaHF(uid="5A 3E 7C 1B", atqa=atqa, sak=sak, familia=familia)


def test_receta_mifare_classic_1k() -> None:
    tarjeta = receta_hf(_hf(FamiliaHF.MIFARE_CLASSIC_1K), "  salida  ", FECHA)

    assert tarjeta.banda is Banda.HF
    assert tarjeta.frecuencia == "HF 13.56 MHz"
    assert tarjeta.tipo == "MIFARE Classic 1K"
    assert tarjeta.seguridad == "Crypto-1 (Requiere autopwn / nested)"
    assert tarjeta.tarjeta_destino == "Magic Card Gen1a / Gen2"
    assert tarjeta.comando_clonado == "hf mf cload -f dump_5A3E7C1B.bin"
    assert tarjeta.comando_emulacion == "hf mf sim --1k -u 5A3E7C1B"
    assert tarjeta.salida == "salida"
    assert tarjeta.fecha == FECHA


def test_receta_mifare_classic_4k() -> None:
    tarjeta = receta_hf(_hf(FamiliaHF.MIFARE_CLASSIC_4K), "", FECHA)

    assert tarjeta.comando_emulacion == "hf mf sim --4k -u 5A3E7C1B"
    assert tarjeta.seguridad == "Cifrado estándar"


def test_receta_ultralight_ntag() -> None:
    tarjeta = receta_hf(_hf(FamiliaHF.ULTRALIGHT_NTAG), "", FECHA)

    assert tarjeta.tipo == "MIFARE Ultralight / NTAG"
    assert tarjeta.tarjeta_destino == "Magic Ultralight / NTAG21x"
    assert tarjeta.comando_clonado == "hf mfu restore -f dump_5A3E7C1B.bin"
    assert tarjeta.comando_emulacion == "hf mfu sim -t 7 -u 5A3E7C1B"


def test_receta_hf_sin_atqa_ni_sak_usa_valores_por_defecto() -> None:
    tarjeta = receta_hf(_hf(FamiliaHF.DESCONOCIDA, atqa=None, sak=None), "", FECHA)

    assert tarjeta.tipo == "ISO14443-A (HF)"
    assert tarjeta.atqa == "00 04"
    assert tarjeta.sak == "08"


def test_receta_em410x() -> None:
    tarjeta = receta_lf(TarjetaLF(id_em="0F0368568B"), "", FECHA)

    assert tarjeta.banda is Banda.LF
    assert tarjeta.frecuencia == "LF 125 kHz"
    assert tarjeta.tipo == "EM410x (EM4100)"
    assert tarjeta.uid == "0F 03 68 56 8B"
    assert tarjeta.tarjeta_destino == "Chip T5577 (125 kHz)"
    assert tarjeta.comando_clonado == "lf em 410x clone --id 0F0368568B"
    assert tarjeta.comando_emulacion == "lf em 410x sim --id 0F0368568B"
