"""Recetas: datos derivados de una tarjeta (tarjeta destino, seguridad y comandos).

Es el ÚNICO sitio donde se generan los comandos de clonado y emulación, a
partir del tipo canónico y del UID/ID. Nunca se ejecuta un comando guardado
en la base de datos ni importado de un archivo (ver normas en CLAUDE.md).
Funciones puras.
"""

from __future__ import annotations

import re

from pm3_dashboard.pm3.modelos import (
    Banda,
    Derivados,
    TarjetaHF,
    TarjetaLeida,
    TarjetaLF,
    TipoTarjeta,
)

ATQA_POR_DEFECTO = "00 04"
SAK_POR_DEFECTO = "08"

_RE_HEX = re.compile(r"[0-9A-F]+")


def _uid_compacto(uid: str) -> str:
    """'5a 3e 7c 1b' -> '5A3E7C1B'. Lanza ValueError si no es hexadecimal.

    Comprobación de seguridad: lo que va dentro de un comando solo puede ser
    hexadecimal, venga de donde venga.
    """
    compacto = "".join(uid.split()).upper()
    if not _RE_HEX.fullmatch(compacto) or len(compacto) % 2:
        raise ValueError(f"UID no válido para generar comandos: {uid!r}")
    return compacto


def uid_con_espacios(uid: str) -> str:
    """'0F0368568B' -> '0F 03 68 56 8B'."""
    compacto = _uid_compacto(uid)
    return " ".join(compacto[i : i + 2] for i in range(0, len(compacto), 2))


def derivados(tipo: TipoTarjeta, uid: str) -> Derivados:
    """Datos derivados del tipo y el UID. Lanza ValueError si el UID no es hexadecimal."""
    tipo = TipoTarjeta(tipo)
    uid = _uid_compacto(uid)

    if tipo is TipoTarjeta.EM410X:
        return Derivados(
            frecuencia="LF 125 kHz",
            tarjeta_destino="Chip T5577 (125 kHz)",
            seguridad="Sin cifrado (Solo UID)",
            comando_clonado=f"lf em 410x clone --id {uid}",
            comando_emulacion=f"lf em 410x sim --id {uid}",
        )

    destino = "Magic Card Gen1a / Gen2"
    seguridad = "Cifrado estándar"
    clonado = f"hf mf cload -f dump_{uid}.bin"
    emulacion = f"hf mf sim --1k -u {uid}"
    if tipo is TipoTarjeta.MIFARE_CLASSIC_1K:
        seguridad = "Crypto-1 (Requiere autopwn / nested)"
    elif tipo is TipoTarjeta.MIFARE_CLASSIC_4K:
        emulacion = f"hf mf sim --4k -u {uid}"
    elif tipo is TipoTarjeta.ULTRALIGHT_NTAG:
        destino = "Magic Ultralight / NTAG21x"
        clonado = f"hf mfu restore -f dump_{uid}.bin"
        emulacion = f"hf mfu sim -t 7 -u {uid}"

    return Derivados(
        frecuencia="HF 13.56 MHz",
        tarjeta_destino=destino,
        seguridad=seguridad,
        comando_clonado=clonado,
        comando_emulacion=emulacion,
    )


def receta_hf(tarjeta: TarjetaHF, salida: str, fecha: str) -> TarjetaLeida:
    return TarjetaLeida(
        fecha=fecha,
        banda=Banda.HF,
        tipo=tarjeta.tipo,
        uid=tarjeta.uid,
        atqa=tarjeta.atqa or ATQA_POR_DEFECTO,
        sak=tarjeta.sak or SAK_POR_DEFECTO,
        salida=salida.strip(),
        derivados=derivados(tarjeta.tipo, tarjeta.uid),
    )


def receta_lf(tarjeta: TarjetaLF, salida: str, fecha: str) -> TarjetaLeida:
    return TarjetaLeida(
        fecha=fecha,
        banda=Banda.LF,
        tipo=TipoTarjeta.EM410X,
        uid=uid_con_espacios(tarjeta.id_em),
        atqa="",  # ATQA/SAK no existen en LF
        sak="",
        salida=salida.strip(),
        derivados=derivados(TipoTarjeta.EM410X, tarjeta.id_em),
    )
