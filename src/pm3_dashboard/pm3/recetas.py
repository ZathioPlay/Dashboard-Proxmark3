"""Recetas: de una tarjeta detectada a los datos para mostrarla, clonarla y emularla.

Funciones puras. Para soportar un tipo nuevo de tarjeta se añade aquí su
receta sin tocar los parsers.
"""

from __future__ import annotations

from pm3_dashboard.pm3.modelos import Banda, FamiliaHF, TarjetaHF, TarjetaLeida, TarjetaLF

ATQA_POR_DEFECTO = "00 04"
SAK_POR_DEFECTO = "08"


def receta_hf(tarjeta: TarjetaHF, salida: str, fecha: str) -> TarjetaLeida:
    uid = tarjeta.uid.replace(" ", "")
    destino = "Magic Card Gen1a / Gen2"
    seguridad = "Cifrado estándar"
    clonado = f"hf mf cload -f dump_{uid}.bin"
    emulacion = f"hf mf sim --1k -u {uid}"

    if tarjeta.familia is FamiliaHF.MIFARE_CLASSIC_1K:
        seguridad = "Crypto-1 (Requiere autopwn / nested)"
    elif tarjeta.familia is FamiliaHF.MIFARE_CLASSIC_4K:
        emulacion = f"hf mf sim --4k -u {uid}"
    elif tarjeta.familia is FamiliaHF.ULTRALIGHT_NTAG:
        destino = "Magic Ultralight / NTAG21x"
        clonado = f"hf mfu restore -f dump_{uid}.bin"
        emulacion = f"hf mfu sim -t 7 -u {uid}"

    return TarjetaLeida(
        fecha=fecha,
        frecuencia="HF 13.56 MHz",
        banda=Banda.HF,
        tipo=tarjeta.familia.value,
        uid=tarjeta.uid,
        atqa=tarjeta.atqa or ATQA_POR_DEFECTO,
        sak=tarjeta.sak or SAK_POR_DEFECTO,
        tarjeta_destino=destino,
        seguridad=seguridad,
        comando_clonado=clonado,
        comando_emulacion=emulacion,
        salida=salida.strip(),
    )


def receta_lf(tarjeta: TarjetaLF, salida: str, fecha: str) -> TarjetaLeida:
    id_em = tarjeta.id_em
    return TarjetaLeida(
        fecha=fecha,
        frecuencia="LF 125 kHz",
        banda=Banda.LF,
        tipo="EM410x (EM4100)",
        uid=" ".join(id_em[i : i + 2] for i in range(0, len(id_em), 2)),
        atqa="ASK / Manchester",
        sak="64-bit ID",
        tarjeta_destino="Chip T5577 (125 kHz)",
        seguridad="Sin cifrado (Solo UID)",
        comando_clonado=f"lf em 410x clone --id {id_em}",
        comando_emulacion=f"lf em 410x sim --id {id_em}",
        salida=salida.strip(),
    )
