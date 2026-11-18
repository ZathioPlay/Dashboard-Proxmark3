"""Localiza el cliente de Iceman (proxmark3.exe / proxmark3).

Orden de búsqueda (se usa el primero que exista):
1. Configurado: 'ruta_cliente' de config.json (o PM3_BIN). Prioridad absoluta:
   si está puesto y no existe, es un error y NO se sigue buscando, para no
   usar sin avisar un cliente distinto del que se eligió.
2. Incluido con la app: vendor/pm3-client (desarrollo) o pm3-client junto al .exe.
3. Sistema: ~/proxmark3, ProxSpace (solo Windows) y el PATH.

Funciones puras: todo lo que toca el sistema (comprobar ficheros, carpeta del
usuario, PATH) se recibe como parámetro, así que los tests usan un sistema de
archivos simulado y nunca el cliente real.

Seguridad: el PATH se recorre aquí en vez de usar shutil.which, que en Windows
busca primero en el directorio actual. Se ignoran las entradas vacías o
relativas para que un proxmark3.exe en la carpeta de trabajo no se ejecute.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PureWindowsPath


class OrigenCliente(StrEnum):
    CONFIGURADO = "configurado"
    INCLUIDO = "incluido"
    SISTEMA = "sistema"


@dataclass(frozen=True)
class UbicacionCliente:
    ruta: Path
    origen: OrigenCliente
    detalle: str  # de dónde sale, en palabras: "config.json", "ProxSpace", "PATH"...
    rutas_extra: tuple[Path, ...] = ()  # carpetas de DLL que necesita (ProxSpace)


@dataclass(frozen=True)
class ResultadoBusqueda:
    """ubicacion es None si no se ha encontrado; 'buscado' dice dónde se ha mirado."""

    ubicacion: UbicacionCliente | None
    buscado: tuple[str, ...] = field(default_factory=tuple)
    configurado_inexistente: Path | None = None


def nombre_ejecutable(windows: bool) -> str:
    return "proxmark3.exe" if windows else "proxmark3"


def raices_proxspace_por_defecto(home: Path) -> list[Path]:
    return [Path("C:/ProxSpace"), home / "ProxSpace"]


def _es_absoluta(entrada: str, windows: bool) -> bool:
    if windows:
        ruta = PureWindowsPath(entrada)
        return bool(ruta.drive) and ruta.is_absolute()
    return entrada.startswith("/")


def carpetas_path(path_sistema: str, windows: bool) -> list[Path]:
    """Entradas del PATH utilizables: absolutas, sin vacías ni relativas (como '.')."""
    separador = ";" if windows else ":"
    carpetas: list[Path] = []
    for entrada in path_sistema.split(separador):
        entrada = entrada.strip().strip('"')
        if entrada and _es_absoluta(entrada, windows):
            carpetas.append(Path(entrada))
    return carpetas


def _candidatos_sistema(
    home: Path,
    raices_proxspace: Sequence[Path],
    path_sistema: str,
    windows: bool,
) -> list[tuple[Path, str, tuple[Path, ...]]]:
    """(ruta, detalle, rutas_extra) en orden de preferencia."""
    exe = nombre_ejecutable(windows)
    candidatos: list[tuple[Path, str, tuple[Path, ...]]] = []

    carpeta_usuario = home / "proxmark3"
    for relativa in (Path("client") / exe, Path("client") / "build" / exe, Path(exe)):
        candidatos.append((carpeta_usuario / relativa, "~/proxmark3", ()))

    if windows:
        for raiz in raices_proxspace:
            # Un cliente compilado en ProxSpace necesita las DLL de su MSYS2.
            dlls = (raiz / "msys2" / "mingw64" / "bin", raiz / "msys2" / "usr" / "bin")
            for relativa in (Path("pm3") / "proxmark3" / "client" / exe, Path("pm3") / "client" / exe):
                candidatos.append((raiz / relativa, "ProxSpace", dlls))

    for carpeta in carpetas_path(path_sistema, windows):
        candidatos.append((carpeta / exe, "PATH", ()))
    return candidatos


def localizar_cliente(
    ruta_configurada: Path | None,
    incluido: Path,
    *,
    home: Path,
    path_sistema: str,
    raices_proxspace: Sequence[Path] | None = None,
    existe: Callable[[Path], bool] = Path.is_file,
    existe_carpeta: Callable[[Path], bool] = Path.is_dir,
    windows: bool = sys.platform == "win32",
) -> ResultadoBusqueda:
    """Busca el cliente en el orden de prioridad. 'existe' debe ser True solo para ficheros."""
    # 1. Configurado: prioridad absoluta.
    if ruta_configurada is not None:
        if existe(ruta_configurada):
            return ResultadoBusqueda(UbicacionCliente(ruta_configurada, OrigenCliente.CONFIGURADO, "config.json"))
        return ResultadoBusqueda(None, (str(ruta_configurada),), configurado_inexistente=ruta_configurada)

    buscado: list[str] = []

    # 2. Incluido con la app.
    buscado.append(str(incluido.parent))
    if existe(incluido):
        return ResultadoBusqueda(UbicacionCliente(incluido, OrigenCliente.INCLUIDO, "incluido con la app"))

    # 3. Sistema.
    raices = list(raices_proxspace) if raices_proxspace is not None else raices_proxspace_por_defecto(home)
    for ruta, detalle, dlls in _candidatos_sistema(home, raices, path_sistema, windows):
        if existe(ruta):
            extra = tuple(carpeta for carpeta in dlls if existe_carpeta(carpeta))
            return ResultadoBusqueda(UbicacionCliente(ruta, OrigenCliente.SISTEMA, detalle, extra))

    buscado.append(str(home / "proxmark3"))
    if windows:
        buscado += [str(raiz) for raiz in raices]
    buscado.append("PATH")
    return ResultadoBusqueda(None, tuple(buscado))


def mensaje_no_encontrado(resultado: ResultadoBusqueda, windows: bool = sys.platform == "win32") -> str:
    """Mensaje para el usuario cuando no hay cliente."""
    if resultado.configurado_inexistente is not None:
        return (
            f"No se encuentra el cliente de Iceman en {resultado.configurado_inexistente} "
            "(configurado en config.json). Revisa 'ruta_cliente' en la configuración."
        )
    return (
        f"No se encuentra el cliente de Iceman ({nombre_ejecutable(windows)}). "
        f"Se ha buscado en: {', '.join(resultado.buscado)}. "
        "Instálalo o indica la ruta en 'ruta_cliente' de la configuración (config.json)."
    )
