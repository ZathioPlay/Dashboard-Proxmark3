"""Parsers de la salida del cliente de Iceman.

Son funciones puras: reciben el texto que imprime el cliente y devuelven
datos (o None si no encuentran nada). No lanzan comandos ni tocan el puerto,
así que se prueban con salidas de ejemplo, sin hardware.
"""

from __future__ import annotations

import re

from pm3_dashboard.pm3.modelos import (
    EstadoAntena,
    InfoVersion,
    MedicionAntena,
    MedicionAntenas,
    TarjetaHF,
    TarjetaLF,
    TipoTarjeta,
)
from pm3_dashboard.pm3.salida import limpiar_salida

# Voltaje mínimo aceptable cuando 'hw tune' no da veredicto (igual que el prototipo).
MINIMO_LF_V = 20.0
MINIMO_HF_V = 18.0

# ---------------------------------------------------------------------------
# hw version
# ---------------------------------------------------------------------------
_PREFIJO = r"^\s*(?:\[.{1,2}\]\s*)?"  # admite "[+] " o "[=] " delante
_RE_CLIENTE = re.compile(_PREFIJO + r"client:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_RE_FIRMWARE = re.compile(_PREFIJO + r"os:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_RE_BOOTROM = re.compile(_PREFIJO + r"bootrom:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_RE_DISPOSITIVO = re.compile(_PREFIJO + r"device\.+\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)


def _buscar(patron: re.Pattern[str], texto: str) -> str:
    coincidencia = patron.search(texto)
    return coincidencia.group(1) if coincidencia else ""


def _version(linea: str) -> str:
    """Primera palabra de la línea: 'RRG/Iceman/master/v4.18994-48-g...'."""
    return linea.split()[0] if linea.split() else ""


def parsear_hw_version(texto: str) -> InfoVersion | None:
    """Extrae versión del cliente, firmware (os), bootrom y modelo.

    El prototipo tomaba el primer 'Iceman/...' como firmware, pero esa línea
    es la del cliente; aquí se separan las dos.
    """
    texto = limpiar_salida(texto)
    cliente = _buscar(_RE_CLIENTE, texto)
    firmware = _buscar(_RE_FIRMWARE, texto)
    if not cliente and not firmware:
        return None
    coinciden = _version(cliente) == _version(firmware) if cliente and firmware else None
    return InfoVersion(
        cliente=cliente,
        firmware=firmware,
        bootrom=_buscar(_RE_BOOTROM, texto),
        dispositivo=_buscar(_RE_DISPOSITIVO, texto),
        versiones_coinciden=coinciden,
    )


# ---------------------------------------------------------------------------
# hw tune
# ---------------------------------------------------------------------------
_RE_CABECERA_HF = re.compile(r"-+\s*HF Antenna", re.IGNORECASE)
_RE_SIGUIENTE_CABECERA = re.compile(r"\n[^\n]*-{3,}\s*\w")
_RE_VOLTIOS = re.compile(r"(\d+(?:\.\d+)?)\s*V\b")
# "LF antenna is OK" (versiones antiguas) o "LF antenna ( ok )" (actuales).
_RE_VEREDICTO = re.compile(r"antenna\s+(?:is\s+)?\(?\s*(ok|marginal|unusable)\b", re.IGNORECASE)
_VEREDICTOS = {
    "ok": EstadoAntena.OK,
    "marginal": EstadoAntena.MARGINAL,
    "unusable": EstadoAntena.INUTILIZABLE,
}


def _secciones_tune(texto: str) -> tuple[str, str]:
    """Divide la salida en la parte LF y la parte HF."""
    partes = _RE_CABECERA_HF.split(texto, maxsplit=1)
    lf = partes[0]
    hf = partes[1] if len(partes) > 1 else ""
    # La parte HF termina en la siguiente cabecera (p. ej. "LF tuning graph").
    hf = _RE_SIGUIENTE_CABECERA.split(hf, maxsplit=1)[0]
    return lf, hf


def _primer_voltaje(texto: str, preferir: str = "") -> float | None:
    """Primer valor en voltios; si se indica, mira antes las líneas que contienen 'preferir'."""
    lineas = texto.splitlines()
    if preferir:
        lineas = [linea for linea in lineas if preferir in linea] + lineas
    for linea in lineas:
        coincidencia = _RE_VOLTIOS.search(linea)
        if coincidencia:
            return float(coincidencia.group(1))
    return None


def _veredicto(texto: str, voltios: float | None, minimo: float) -> EstadoAntena:
    coincidencia = _RE_VEREDICTO.search(texto)
    if coincidencia:
        return _VEREDICTOS[coincidencia.group(1).lower()]
    if voltios is None:
        return EstadoAntena.SIN_DATOS
    return EstadoAntena.OK if voltios >= minimo else EstadoAntena.BAJA


def parsear_hw_tune(texto: str) -> MedicionAntenas:
    """Voltaje y estado de las antenas LF (a 125 kHz) y HF (13.56 MHz)."""
    lf_texto, hf_texto = _secciones_tune(limpiar_salida(texto))
    lf_v = _primer_voltaje(lf_texto, preferir="125")
    hf_v = _primer_voltaje(hf_texto)
    return MedicionAntenas(
        lf=MedicionAntena(voltios=lf_v, estado=_veredicto(lf_texto, lf_v, MINIMO_LF_V)),
        hf=MedicionAntena(voltios=hf_v, estado=_veredicto(hf_texto, hf_v, MINIMO_HF_V)),
    )


# ---------------------------------------------------------------------------
# hf search
# ---------------------------------------------------------------------------
# Solo hasta el final de la línea (el prototipo podía saltar a la siguiente).
_RE_UID = re.compile(r"\bUID\s*:\s*([0-9A-Fa-f]+(?:[ \t]+[0-9A-Fa-f]+)*)")
_RE_ATQA = re.compile(r"\bATQA\s*:\s*([0-9A-Fa-f]+(?:[ \t]+[0-9A-Fa-f]+)*)")
_RE_SAK = re.compile(r"\bSAK\s*:\s*([0-9A-Fa-f]+)")


def _hex_con_espacios(valor: str) -> str:
    return " ".join(valor.split()).upper()


def _tipo_hf(texto: str) -> TipoTarjeta:
    # Mismo orden de comprobación que el prototipo.
    if "MIFARE Classic 1K" in texto:
        return TipoTarjeta.MIFARE_CLASSIC_1K
    if "MIFARE Classic 4K" in texto:
        return TipoTarjeta.MIFARE_CLASSIC_4K
    if "Ultralight" in texto or "NTAG" in texto:
        return TipoTarjeta.ULTRALIGHT_NTAG
    return TipoTarjeta.ISO14443A


def parsear_hf_search(texto: str) -> TarjetaHF | None:
    """Tarjeta ISO14443-A encontrada por 'hf search', o None si no hay."""
    texto = limpiar_salida(texto)
    uid = _RE_UID.search(texto)
    if not uid:
        return None
    atqa = _RE_ATQA.search(texto)
    sak = _RE_SAK.search(texto)
    return TarjetaHF(
        uid=_hex_con_espacios(uid.group(1)),
        atqa=_hex_con_espacios(atqa.group(1)) if atqa else None,
        sak=sak.group(1).upper() if sak else None,
        tipo=_tipo_hf(texto),
    )


# ---------------------------------------------------------------------------
# lf search
# ---------------------------------------------------------------------------
_RES_EM410X = (
    # Actual: "[+] EM 410x ID 0F0368568B"
    re.compile(r"EM\s*410x.*?ID\s*[:\-]?\s*([0-9A-Fa-f]{10})(?![0-9A-Fa-f])", re.IGNORECASE),
    # Antiguo: "EM TAG ID      : 0F0368568B"
    re.compile(r"EM TAG ID\s*:\s*([0-9A-Fa-f]{10})(?![0-9A-Fa-f])", re.IGNORECASE),
)


def parsear_lf_search(texto: str) -> TarjetaLF | None:
    """Tarjeta EM410x encontrada por 'lf search', o None si no hay."""
    texto = limpiar_salida(texto)
    for patron in _RES_EM410X:
        coincidencia = patron.search(texto)
        if coincidencia:
            return TarjetaLF(id_em=coincidencia.group(1).upper())
    return None
