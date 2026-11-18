"""Decodificadores de la memoria de una tarjeta (funciones puras: bytes/hex -> datos).

Se usan para enriquecer la lectura de bloques: texto ASCII, claves y bits de
acceso de MIFARE Classic, y registros NDEF de NTAG/Ultralight. No ejecutan nada
ni tocan el hardware, así que se prueban con volcados de ejemplo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_RE_HEX = re.compile(r"[0-9A-Fa-f]*$")


def _bytes_de_hex(hexa: str) -> bytes | None:
    """'5A 3E 7C' -> b'\\x5a\\x3e\\x7c'. None si no es hexadecimal con nº par de dígitos."""
    compacto = "".join(hexa.split())
    if not _RE_HEX.fullmatch(compacto) or len(compacto) % 2:
        return None
    return bytes.fromhex(compacto)


# ---------------------------------------------------------------------------
# ASCII
# ---------------------------------------------------------------------------
def ascii_de_hex(hexa: str) -> str:
    """Cada byte imprimible (0x20-0x7E) como carácter; el resto como '.', como Iceman."""
    datos = _bytes_de_hex(hexa)
    if datos is None:
        return ""
    return "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in datos)


# ---------------------------------------------------------------------------
# MIFARE Classic: claves y bits de acceso del trailer
# ---------------------------------------------------------------------------
def claves_de_trailer(hex_trailer: str) -> tuple[str | None, str | None]:
    """Clave A (bytes 0-5) y Clave B (bytes 10-15) del bloque trailer de un sector."""
    datos = _bytes_de_hex(hex_trailer)
    if datos is None or len(datos) != 16:
        return None, None
    clave_a = datos[0:6].hex().upper()
    clave_b = datos[10:16].hex().upper()
    return clave_a, clave_b


def _condiciones_acceso(datos: bytes) -> list[tuple[int, int, int]] | None:
    """(C1, C2, C3) de los bloques 0..3 del sector, o None si la copia invertida no cuadra."""
    b6, b7, b8 = datos[6], datos[7], datos[8]
    c1 = (b7 >> 4) & 0xF
    c2 = b8 & 0xF
    c3 = (b8 >> 4) & 0xF
    inv_c1 = b6 & 0xF
    inv_c2 = (b6 >> 4) & 0xF
    inv_c3 = b7 & 0xF
    # Los tres nibbles se guardan también invertidos como control de integridad.
    if inv_c1 != (~c1 & 0xF) or inv_c2 != (~c2 & 0xF) or inv_c3 != (~c3 & 0xF):
        return None
    return [((c1 >> n) & 1, (c2 >> n) & 1, (c3 >> n) & 1) for n in range(4)]


# Qué permite un bloque de datos según (C1, C2, C3) (tabla estándar MIFARE Classic).
_ACCESO_DATOS = {
    (0, 0, 0): "lectura y escritura con clave A o B",
    (0, 1, 0): "solo lectura con clave A o B",
    (1, 0, 0): "lectura con A o B; escritura con clave B",
    (1, 1, 0): "lectura con A o B; escritura, incremento y decremento con clave B",
    (0, 0, 1): "lectura con A o B; decremento con A o B (bloque de valor)",
    (0, 1, 1): "lectura y escritura solo con clave B",
    (1, 0, 1): "solo lectura con clave B",
    (1, 1, 1): "sin acceso",
}
# Qué permite el bloque trailer según (C1, C2, C3).
_ACCESO_TRAILER = {
    (0, 0, 0): "clave A: escritura; bits de acceso: lectura con A; clave B: lectura y escritura con A",
    (0, 1, 0): "clave A: sin acceso; bits de acceso: lectura con A; clave B: lectura con A",
    (1, 0, 0): "clave A: escritura con B; bits de acceso: lectura con A o B; clave B: escritura con B",
    (1, 1, 0): "clave A: sin acceso; bits de acceso: lectura con A o B; clave B: sin acceso",
    (0, 0, 1): "clave A: escritura; bits de acceso: lectura y escritura con A; clave B: lectura y escritura con A",
    (0, 1, 1): "clave A: escritura con B; bits de acceso: lectura con A o B, escritura con B; clave B: escritura con B",
    (1, 0, 1): "clave A: sin acceso; bits de acceso: lectura con A o B, escritura con B; clave B: sin acceso",
    (1, 1, 1): "clave A: sin acceso; bits de acceso: lectura con A o B; clave B: sin acceso",
}


def accesos_coherentes(hex_trailer: str) -> bool:
    """True si los bytes de acceso (6-8) y su copia invertida cuadran."""
    datos = _bytes_de_hex(hex_trailer)
    return datos is not None and len(datos) == 16 and _condiciones_acceso(datos) is not None


def accesos_de_trailer(hex_trailer: str) -> list[str] | None:
    """Qué permite cada bloque del sector, en palabras. None si no se puede interpretar.

    Devuelve 4 frases (bloques 0, 1, 2 y el trailer) para un sector de 4 bloques.
    """
    datos = _bytes_de_hex(hex_trailer)
    if datos is None or len(datos) != 16:
        return None
    condiciones = _condiciones_acceso(datos)
    if condiciones is None:
        return None
    frases = [_ACCESO_DATOS[condiciones[n]] for n in range(3)]
    frases.append(_ACCESO_TRAILER[condiciones[3]])
    return frases


# ---------------------------------------------------------------------------
# NTAG / Ultralight: registros NDEF
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RegistroNdef:
    tipo: str  # "texto" | "uri" | "otro"
    contenido: str


# Prefijos de URI del estándar NDEF (los más usados).
_PREFIJOS_URI = {
    0x00: "", 0x01: "http://www.", 0x02: "https://www.", 0x03: "http://",
    0x04: "https://", 0x05: "tel:", 0x06: "mailto:", 0x07: "ftp://anonymous:anonymous@",
    0x08: "ftp://ftp.", 0x09: "ftps://", 0x0D: "ftp://",
}


def _texto_record(payload: bytes) -> str:
    if not payload:
        return ""
    longitud_idioma = payload[0] & 0x3F
    texto = payload[1 + longitud_idioma :]
    codificacion = "utf-16" if payload[0] & 0x80 else "utf-8"
    try:
        return texto.decode(codificacion, errors="replace")
    except LookupError:
        return texto.decode("utf-8", errors="replace")


def _uri_record(payload: bytes) -> str:
    if not payload:
        return ""
    prefijo = _PREFIJOS_URI.get(payload[0], "")
    return prefijo + payload[1:].decode("utf-8", errors="replace")


def _registros_ndef(mensaje: bytes) -> list[RegistroNdef]:
    registros: list[RegistroNdef] = []
    i = 0
    while i < len(mensaje):
        cabecera = mensaje[i]
        es_corto = bool(cabecera & 0x10)  # SR: longitud de payload en 1 byte
        con_id = bool(cabecera & 0x08)
        tnf = cabecera & 0x07
        i += 1
        if i >= len(mensaje):
            break
        long_tipo = mensaje[i]
        i += 1
        if es_corto:
            long_payload = mensaje[i]
            i += 1
        else:
            long_payload = int.from_bytes(mensaje[i : i + 4], "big")
            i += 4
        long_id = 0
        if con_id:
            long_id = mensaje[i]
            i += 1
        tipo = mensaje[i : i + long_tipo]
        i += long_tipo + long_id
        payload = mensaje[i : i + long_payload]
        i += long_payload

        if tnf == 0x01 and tipo == b"T":
            registros.append(RegistroNdef("texto", _texto_record(payload)))
        elif tnf == 0x01 and tipo == b"U":
            registros.append(RegistroNdef("uri", _uri_record(payload)))
        else:
            registros.append(RegistroNdef("otro", payload.hex().upper()))

        if cabecera & 0x40:  # ME: último registro del mensaje
            break
    return registros


def decodificar_ndef(paginas_hex: list[str]) -> list[RegistroNdef]:
    """Registros NDEF (texto y URLs) de la memoria de usuario de un NTAG/Ultralight.

    Recorre el área TLV desde la página 4. Sin mensaje NDEF, devuelve [].
    """
    partes = [_bytes_de_hex(p) for p in paginas_hex[4:]]
    memoria = b"".join(p for p in partes if p is not None)

    i = 0
    while i < len(memoria):
        etiqueta = memoria[i]
        if etiqueta == 0x00:  # NULL
            i += 1
            continue
        if etiqueta == 0xFE:  # terminador
            break
        if i + 1 >= len(memoria):
            break
        longitud = memoria[i + 1]
        inicio = i + 2
        if longitud == 0xFF:  # longitud en 2 bytes
            longitud = int.from_bytes(memoria[i + 2 : i + 4], "big")
            inicio = i + 4
        if etiqueta == 0x03:  # mensaje NDEF
            return _registros_ndef(memoria[inicio : inicio + longitud])
        i = inicio + longitud  # otros TLV (lock, memory control, propietario): se saltan
    return []
