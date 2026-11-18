"""Configuración de la aplicación (%APPDATA%\\PM3-Dashboard\\config.json).

Ejemplo de config.json:

    {
      "ruta_cliente": "C:/ProxSpace/pm3/proxmark3/client/proxmark3.exe",
      "puerto": "auto",
      "rutas_extra": ["C:/ProxSpace/msys2/mingw64/bin", "C:/ProxSpace/msys2/usr/bin"]
    }

- ruta_cliente: vacío = se busca automáticamente (incluido con la app,
  ~/proxmark3, ProxSpace, PATH; ver pm3/localizador.py). Si se indica, tiene
  prioridad absoluta. Relativa = desde la carpeta de la app.
- puerto: "auto" para detectarlo, o "COM3", "COM4"...
- rutas_extra: carpetas que se añaden al PATH al lanzar el cliente (DLL).

Las variables de entorno PM3_BIN y PM3_PORT tienen prioridad sobre el fichero.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pm3_dashboard import paths

PUERTO_AUTO = "auto"


@dataclass
class ConfigPm3:
    """Ajustes para lanzar el cliente de Iceman."""

    ruta_cliente: str = ""
    puerto: str = PUERTO_AUTO
    rutas_extra: list[str] = field(default_factory=list)


def _leer_json(ruta: Path) -> dict:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _aplicar_fichero(config: ConfigPm3, datos: dict) -> None:
    """Copia los valores válidos del JSON; los incorrectos se ignoran."""
    if isinstance(datos.get("ruta_cliente"), str):
        config.ruta_cliente = datos["ruta_cliente"].strip()
    if isinstance(datos.get("puerto"), str) and datos["puerto"].strip():
        config.puerto = datos["puerto"].strip()
    if isinstance(datos.get("rutas_extra"), list):
        config.rutas_extra = [r for r in datos["rutas_extra"] if isinstance(r, str) and r.strip()]


def _aplicar_entorno(config: ConfigPm3) -> None:
    if os.getenv("PM3_BIN"):
        config.ruta_cliente = os.environ["PM3_BIN"]
    if os.getenv("PM3_PORT"):
        config.puerto = os.environ["PM3_PORT"]


def cargar_config(ruta: Path | None = None) -> ConfigPm3:
    """Lee la configuración. Si el fichero no existe o está mal, usa los valores por defecto."""
    config = ConfigPm3()
    _aplicar_fichero(config, _leer_json(ruta or paths.ruta_config()))
    _aplicar_entorno(config)
    return config


def guardar_config(config: ConfigPm3, ruta: Path | None = None) -> None:
    """Escribe la configuración en config.json."""
    ruta = ruta or paths.ruta_config()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")


def _resolver(ruta_texto: str) -> Path:
    """Expande variables (%APPDATA%, ~) y resuelve rutas relativas desde la carpeta de la app."""
    ruta = Path(os.path.expandvars(os.path.expanduser(ruta_texto.strip())))
    return ruta if ruta.is_absolute() else (paths.carpeta_app() / ruta).resolve()


def resolver_ruta_configurada(config: ConfigPm3) -> Path | None:
    """Ruta absoluta del cliente indicada en la configuración, o None si no hay ninguna.

    Si es None, pm3/localizador.py busca el cliente automáticamente.
    """
    if not config.ruta_cliente.strip():
        return None
    return _resolver(config.ruta_cliente)


def resolver_rutas_extra(config: ConfigPm3) -> list[Path]:
    """Rutas absolutas de las carpetas extra para el PATH."""
    return [_resolver(r) for r in config.rutas_extra]
