"""Rutas de la aplicación.

Resuelve dónde están los recursos de la interfaz (que cambian según se ejecute
en desarrollo o empaquetado con PyInstaller) y dónde se guardan los datos del
usuario (%APPDATA%\\PM3-Dashboard), fuera de la carpeta del programa.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

NOMBRE_CARPETA_DATOS = "PM3-Dashboard"


def esta_empaquetada() -> bool:
    """Indica si la app se ejecuta como .exe generado por PyInstaller."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def carpeta_paquete() -> Path:
    """Carpeta del paquete pm3_dashboard (en desarrollo o dentro del .exe)."""
    if esta_empaquetada():
        # PyInstaller descomprime los datos en sys._MEIPASS; el .spec debe
        # copiar la interfaz a <_MEIPASS>/pm3_dashboard/ui.
        return Path(sys._MEIPASS) / "pm3_dashboard"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def carpeta_app() -> Path:
    """Carpeta base de la aplicación.

    En desarrollo es la raíz del proyecto; empaquetada, la carpeta del .exe.
    Las rutas relativas de la configuración se resuelven desde aquí.
    """
    if esta_empaquetada():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def ruta_cliente_por_defecto() -> Path:
    """Cliente de Iceman incluido con la app (proxmark3.exe en Windows, proxmark3 en Linux/Mac).

    Empaquetada: <carpeta del .exe>\\pm3-client (lo instala Inno Setup).
    Desarrollo: vendor/pm3-client.
    """
    ejecutable = "proxmark3.exe" if sys.platform == "win32" else "proxmark3"
    if esta_empaquetada():
        return carpeta_app() / "pm3-client" / ejecutable
    return carpeta_app() / "vendor" / "pm3-client" / ejecutable


def carpeta_ui() -> Path:
    """Carpeta con index.html, css/, js/ y assets/."""
    return carpeta_paquete() / "ui"


def ruta_index() -> Path:
    """Ruta del index.html que carga la ventana."""
    return carpeta_ui() / "index.html"


def carpeta_datos() -> Path:
    """Carpeta de datos del usuario (%APPDATA%\\PM3-Dashboard). Se crea si no existe."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    carpeta = base / NOMBRE_CARPETA_DATOS
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def ruta_bd() -> Path:
    """Ruta de la base de datos SQLite."""
    return carpeta_datos() / "pm3.db"


def ruta_config() -> Path:
    """Ruta del fichero de configuración."""
    return carpeta_datos() / "config.json"


def carpeta_dumps() -> Path:
    """Carpeta de trabajo del cliente de Iceman (ahí guarda .bin/.json/.eml)."""
    carpeta = carpeta_datos() / "dumps"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta
