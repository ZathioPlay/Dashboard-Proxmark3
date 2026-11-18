"""Detección del puerto serie (COM) de la Proxmark3."""

from __future__ import annotations

import glob
import sys
from collections.abc import Callable, Sequence
from types import ModuleType

# Identificadores USB (VID, PID) con los que se presenta la Proxmark3.
PM3_USB_IDS = frozenset({(0x9AC4, 0x4B8F), (0x2D2D, 0x504D)})

Detector = Callable[[], str | None]


def puerto_con_pyserial() -> str | None:
    """Usa pyserial si está instalado (es opcional)."""
    try:
        from serial.tools import list_ports  # pyright: ignore[reportMissingImports]
    except ImportError:
        return None
    for puerto in list_ports.comports():
        if (puerto.vid, puerto.pid) in PM3_USB_IDS:
            return puerto.device
    return None


def _puertos_serie_conectados(winreg: ModuleType) -> set[str]:
    conectados: set[str] = set()
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as clave:
        indice = 0
        while True:
            try:
                conectados.add(str(winreg.EnumValue(clave, indice)[1]).upper())
            except OSError:
                return conectados
            indice += 1


def _puertos_de_dispositivo(winreg: ModuleType, vid: int, pid: int) -> list[str]:
    """Puertos COM que Windows ha asignado alguna vez a ese VID/PID."""
    base = rf"SYSTEM\CurrentControlSet\Enum\USB\VID_{vid:04X}&PID_{pid:04X}"
    puertos: list[str] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as clave:
            indice = 0
            while True:
                try:
                    instancia = winreg.EnumKey(clave, indice)
                except OSError:
                    return puertos
                indice += 1
                try:
                    with winreg.OpenKey(clave, instancia + r"\Device Parameters") as parametros:
                        puertos.append(str(winreg.QueryValueEx(parametros, "PortName")[0]).upper())
                except OSError:
                    continue
    except OSError:
        return puertos


def puerto_con_registro_windows() -> str | None:
    """Busca en el registro de Windows el COM asignado a la Proxmark3 que esté conectado ahora."""
    try:
        import winreg
    except ImportError:
        return None
    try:
        conectados = _puertos_serie_conectados(winreg)
    except OSError:
        return None
    for vid, pid in sorted(PM3_USB_IDS):
        for puerto in _puertos_de_dispositivo(winreg, vid, pid):
            if puerto in conectados:
                return puerto
    return None


def puerto_en_linux() -> str | None:
    candidatos = sorted(glob.glob("/dev/serial/by-id/*roxmark*")) or sorted(glob.glob("/dev/ttyACM*"))
    return candidatos[0] if candidatos else None


def detectores_por_defecto() -> list[Detector]:
    detectores: list[Detector] = [puerto_con_pyserial]
    if sys.platform == "win32":
        detectores.append(puerto_con_registro_windows)
    elif sys.platform.startswith("linux"):
        detectores.append(puerto_en_linux)
    return detectores


def detectar_puerto(puerto_config: str | None, detectores: Sequence[Detector] | None = None) -> str | None:
    """Puerto a usar: el de la configuración, o el detectado si es "auto".

    Devuelve None si no se encuentra ninguna Proxmark3.
    """
    puerto = (puerto_config or "auto").strip()
    if puerto.lower() != "auto":
        return puerto
    for detector in detectores if detectores is not None else detectores_por_defecto():
        try:
            encontrado = detector()
        except Exception:  # un detector que falla no debe impedir probar el siguiente
            continue
        if encontrado:
            return encontrado
    return None


# ---------------------------------------------------------------------------
# Comprobación ligera de presencia (no abre el puerto ni lanza el cliente)
# ---------------------------------------------------------------------------
def puertos_presentes() -> set[str] | None:
    """Puertos serie presentes ahora (en mayúsculas), o None si no se puede saber."""
    try:
        from serial.tools import list_ports  # pyright: ignore[reportMissingImports]
    except ImportError:
        pass
    else:
        return {str(p.device).upper() for p in list_ports.comports()}
    if sys.platform == "win32":
        try:
            import winreg

            return _puertos_serie_conectados(winreg)
        except OSError:
            return None
    return None


def puerto_presente(
    puerto_config: str | None,
    detectores: Sequence[Detector] | None = None,
    presentes: Callable[[], set[str] | None] = puertos_presentes,
) -> str | None:
    """Puerto de la Proxmark3 si ahora mismo está conectada, o None.

    Con "auto" se usa la detección por VID/PID. Con un puerto fijo se mira si
    existe; si el sistema no permite saberlo, se da por presente.
    """
    puerto = (puerto_config or "auto").strip()
    if puerto.lower() == "auto":
        return detectar_puerto("auto", detectores)
    try:
        lista = presentes()
    except Exception:
        lista = None
    if lista is None or puerto.upper() in lista:
        return puerto
    return None
