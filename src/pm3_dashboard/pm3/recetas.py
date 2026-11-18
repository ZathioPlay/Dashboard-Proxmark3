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
    Tecnologia,
    TipoTarjeta,
)

ATQA_POR_DEFECTO = "00 04"
SAK_POR_DEFECTO = "08"
CLAVE_POR_DEFECTO = "FFFFFFFFFFFF"

_RE_HEX = re.compile(r"[0-9A-F]+")

BYTES_POR_BLOQUE = {
    Tecnologia.MIFARE_CLASSIC: 16,
    Tecnologia.MIFARE_ULTRALIGHT: 4,
}


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


def nombre_archivo_volcado(uid: str) -> str:
    """Nombre del .bin para clonar. Seguridad: solo el UID validado como hexadecimal.

    Nunca se usa el UID en crudo (podría llevar separadores de ruta o un comando):
    _uid_compacto() garantiza que solo contiene [0-9A-F], así que el nombre no
    puede escaparse de la carpeta de destino.
    """
    return f"dump_{_uid_compacto(uid)}.bin"


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


# ---------------------------------------------------------------------------
# Escritura de bloques (laboratorio): comandos validados a partir de datos puros
# ---------------------------------------------------------------------------
def _hex_exacto(valor: str, n_bytes: int, nombre: str) -> str:
    """Normaliza a hex en mayúsculas sin espacios y exige la longitud exacta.

    Lanza ValueError si no es hexadecimal o no mide n_bytes. Es la barrera de
    seguridad: lo que va dentro de un comando solo puede ser hexadecimal.
    """
    compacto = "".join(valor.split()).upper()
    if not _RE_HEX.fullmatch(compacto):
        raise ValueError(f"{nombre}: solo se admiten dígitos hexadecimales.")
    if len(compacto) != n_bytes * 2:
        raise ValueError(f"{nombre}: deben ser exactamente {n_bytes} bytes ({n_bytes * 2} dígitos hex).")
    return compacto


def bytes_por_bloque(tecnologia: Tecnologia) -> int:
    return BYTES_POR_BLOQUE[Tecnologia(tecnologia)]


def normalizar_datos_bloque(tecnologia: Tecnologia, datos_hex: str) -> str:
    """Valida los datos de un bloque (hex y longitud exacta) y los devuelve compactos."""
    return _hex_exacto(datos_hex, BYTES_POR_BLOQUE[Tecnologia(tecnologia)], "Datos del bloque")


def es_trailer(indice: int, tipo: TipoTarjeta) -> bool:
    """¿El bloque es un trailer de sector (guarda claves y bits de acceso)?

    1K: un trailer cada 4 bloques (3, 7, ..., 63).
    4K: los sectores 0-31 son de 4 bloques (trailer en %4==3) y los sectores
    32-39 son de 16 bloques (trailer en 143, 159, ..., 255).
    """
    tipo = TipoTarjeta(tipo)
    if tipo not in (TipoTarjeta.MIFARE_CLASSIC_1K, TipoTarjeta.MIFARE_CLASSIC_4K):
        return False
    if indice < 128:
        return indice % 4 == 3
    return (indice - 128) % 16 == 15


def texto_a_hex(texto: str, n_bytes: int) -> str:
    """Convierte texto a hex (UTF-8), rellenando con 00 o truncando a n_bytes.

    Devuelve el hex compacto en mayúsculas, para mostrarlo antes de escribir.
    """
    crudo = texto.encode("utf-8")[:n_bytes].ljust(n_bytes, b"\x00")
    return crudo.hex().upper()


def _indice_valido(indice: int) -> int:
    if not isinstance(indice, int) or isinstance(indice, bool) or indice < 0:
        raise ValueError("El número de bloque debe ser un entero no negativo.")
    return indice


def comando_escribir_bloque(
    tecnologia: Tecnologia,
    indice: int,
    datos_hex: str,
    clave: str = CLAVE_POR_DEFECTO,
    usar_clave_b: bool = False,
) -> str:
    """Comando para escribir un bloque. Valida datos (hex y longitud exacta) y clave."""
    tecnologia = Tecnologia(tecnologia)
    indice = _indice_valido(indice)
    datos = _hex_exacto(datos_hex, BYTES_POR_BLOQUE[tecnologia], "Datos del bloque")
    if tecnologia is Tecnologia.MIFARE_ULTRALIGHT:
        return f"hf mfu wrbl -b {indice} -d {datos}"
    clave_hex = _hex_exacto(clave, 6, "Clave")
    tipo_clave = "-b" if usar_clave_b else "-a"
    return f"hf mf wrbl --blk {indice} {tipo_clave} -k {clave_hex} -d {datos}"


def comando_leer_bloque(
    tecnologia: Tecnologia,
    indice: int,
    clave: str = CLAVE_POR_DEFECTO,
    usar_clave_b: bool = False,
) -> str:
    """Comando para releer un solo bloque y verificar una escritura."""
    tecnologia = Tecnologia(tecnologia)
    indice = _indice_valido(indice)
    if tecnologia is Tecnologia.MIFARE_ULTRALIGHT:
        return f"hf mfu rdbl -b {indice}"
    clave_hex = _hex_exacto(clave, 6, "Clave")
    tipo_clave = "-b" if usar_clave_b else "-a"
    return f"hf mf rdbl --blk {indice} {tipo_clave} -k {clave_hex}"
