"""Tests del localizador del cliente de Iceman con un sistema de archivos simulado.

Nunca se toca el disco real ni se ejecuta ningún cliente: 'existe' y
'existe_carpeta' consultan conjuntos de rutas inventadas.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pm3_dashboard.pm3.localizador import (
    OrigenCliente,
    ResultadoBusqueda,
    carpetas_path,
    localizar_cliente,
    mensaje_no_encontrado,
)

HOME = Path("C:/Users/ana")
INCLUIDO = Path("C:/Program Files/PM3 Dashboard/pm3-client/proxmark3.exe")
CONFIGURADO = Path("D:/herramientas/iceman/proxmark3.exe")
USUARIO = HOME / "proxmark3" / "client" / "proxmark3.exe"
USUARIO_BUILD = HOME / "proxmark3" / "client" / "build" / "proxmark3.exe"
USUARIO_RAIZ = HOME / "proxmark3" / "proxmark3.exe"
PROXSPACE = Path("C:/ProxSpace/pm3/proxmark3/client/proxmark3.exe")
PROXSPACE_ANTIGUO = Path("C:/ProxSpace/pm3/client/proxmark3.exe")
PROXSPACE_USUARIO = HOME / "ProxSpace" / "pm3" / "proxmark3" / "client" / "proxmark3.exe"
EN_PATH = Path("C:/iceman/bin/proxmark3.exe")
PATH_WINDOWS = "C:\\Windows\\system32;C:\\iceman\\bin"

TODOS = {CONFIGURADO, INCLUIDO, USUARIO, USUARIO_BUILD, USUARIO_RAIZ, PROXSPACE, PROXSPACE_ANTIGUO,
         PROXSPACE_USUARIO, EN_PATH}


class SistemaSimulado:
    """Ficheros y carpetas que 'existen'. Una carpeta llamada proxmark3.exe no es un fichero."""

    def __init__(self, ficheros: set[Path], carpetas: set[Path] = frozenset()) -> None:
        self.ficheros = set(ficheros)
        self.carpetas = set(carpetas)
        self.consultas: list[Path] = []

    def existe(self, ruta: Path) -> bool:
        self.consultas.append(ruta)
        return ruta in self.ficheros

    def existe_carpeta(self, ruta: Path) -> bool:
        return ruta in self.carpetas


def _buscar(
    sistema: SistemaSimulado,
    configurado: Path | None = None,
    path: str = PATH_WINDOWS,
    windows: bool = True,
    home: Path = HOME,
    incluido: Path = INCLUIDO,
) -> ResultadoBusqueda:
    return localizar_cliente(
        configurado,
        incluido,
        home=home,
        path_sistema=path,
        existe=sistema.existe,
        existe_carpeta=sistema.existe_carpeta,
        windows=windows,
    )


# ---------------------------------------------------------------- prioridad


@pytest.mark.parametrize(
    ("quitados", "esperado", "origen", "detalle"),
    [
        (set(), INCLUIDO, OrigenCliente.INCLUIDO, "incluido con la app"),
        ({INCLUIDO}, USUARIO, OrigenCliente.SISTEMA, "~/proxmark3"),
        ({INCLUIDO, USUARIO}, USUARIO_BUILD, OrigenCliente.SISTEMA, "~/proxmark3"),
        ({INCLUIDO, USUARIO, USUARIO_BUILD}, USUARIO_RAIZ, OrigenCliente.SISTEMA, "~/proxmark3"),
        ({INCLUIDO, USUARIO, USUARIO_BUILD, USUARIO_RAIZ}, PROXSPACE, OrigenCliente.SISTEMA, "ProxSpace"),
        ({INCLUIDO, USUARIO, USUARIO_BUILD, USUARIO_RAIZ, PROXSPACE}, PROXSPACE_ANTIGUO, OrigenCliente.SISTEMA, "ProxSpace"),
        (
            {INCLUIDO, USUARIO, USUARIO_BUILD, USUARIO_RAIZ, PROXSPACE, PROXSPACE_ANTIGUO},
            PROXSPACE_USUARIO, OrigenCliente.SISTEMA, "ProxSpace",
        ),
        (
            {INCLUIDO, USUARIO, USUARIO_BUILD, USUARIO_RAIZ, PROXSPACE, PROXSPACE_ANTIGUO, PROXSPACE_USUARIO},
            EN_PATH, OrigenCliente.SISTEMA, "PATH",
        ),
    ],
)
def test_orden_de_prioridad_sin_configuracion(
    quitados: set[Path], esperado: Path, origen: OrigenCliente, detalle: str
) -> None:
    ubicacion = _buscar(SistemaSimulado(TODOS - {CONFIGURADO} - quitados)).ubicacion

    assert ubicacion is not None
    assert ubicacion.ruta == esperado
    assert ubicacion.origen is origen
    assert ubicacion.detalle == detalle


def test_config_json_gana_siempre() -> None:
    ubicacion = _buscar(SistemaSimulado(TODOS), configurado=CONFIGURADO).ubicacion

    assert ubicacion is not None
    assert ubicacion.ruta == CONFIGURADO
    assert ubicacion.origen is OrigenCliente.CONFIGURADO
    assert ubicacion.detalle == "config.json"


def test_config_json_inexistente_es_error_y_no_sigue_buscando() -> None:
    sistema = SistemaSimulado(TODOS - {CONFIGURADO})

    resultado = _buscar(sistema, configurado=CONFIGURADO)

    assert resultado.ubicacion is None
    assert resultado.configurado_inexistente == CONFIGURADO
    assert sistema.consultas == [CONFIGURADO]  # no ha mirado en ningún otro sitio
    mensaje = mensaje_no_encontrado(resultado, windows=True)
    assert str(CONFIGURADO) in mensaje and "configurado en config.json" in mensaje


def test_ninguno_encontrado() -> None:
    resultado = _buscar(SistemaSimulado(set()))

    assert resultado.ubicacion is None
    assert resultado.configurado_inexistente is None
    assert resultado.buscado == (
        str(INCLUIDO.parent),
        str(HOME / "proxmark3"),
        str(Path("C:/ProxSpace")),
        str(HOME / "ProxSpace"),
        "PATH",
    )
    mensaje = mensaje_no_encontrado(resultado, windows=True)
    assert mensaje.startswith("No se encuentra el cliente de Iceman (proxmark3.exe). Se ha buscado en: ")
    assert "ruta_cliente" in mensaje


# ---------------------------------------------------------------- solo ficheros


def test_una_carpeta_con_el_nombre_del_ejecutable_no_cuenta() -> None:
    # En ~/proxmark3/client/ hay una CARPETA llamada proxmark3.exe: se sigue buscando.
    sistema = SistemaSimulado({PROXSPACE}, carpetas={USUARIO, INCLUIDO})

    ubicacion = _buscar(sistema).ubicacion

    assert ubicacion is not None and ubicacion.ruta == PROXSPACE


def test_por_defecto_solo_valen_ficheros_reales(tmp_path: Path) -> None:
    """Sin simular: con Path.is_file, una carpeta no se da por buena."""
    carpeta = tmp_path / "pm3-client" / "proxmark3.exe"
    carpeta.mkdir(parents=True)

    resultado = localizar_cliente(None, carpeta, home=tmp_path, path_sistema="", raices_proxspace=[], windows=True)

    assert resultado.ubicacion is None


# ---------------------------------------------------------------- ProxSpace


def test_proxspace_anade_sus_dll_si_existen() -> None:
    mingw = Path("C:/ProxSpace/msys2/mingw64/bin")
    sistema = SistemaSimulado({PROXSPACE}, carpetas={mingw})  # usr/bin no existe

    ubicacion = _buscar(sistema).ubicacion

    assert ubicacion is not None
    assert ubicacion.rutas_extra == (mingw,)


def test_los_demas_origenes_no_anaden_dll() -> None:
    ubicacion = _buscar(SistemaSimulado({EN_PATH}, carpetas={Path("C:/ProxSpace/msys2/mingw64/bin")})).ubicacion

    assert ubicacion is not None and ubicacion.rutas_extra == ()


# ---------------------------------------------------------------- PATH


def test_path_ignora_entradas_vacias_y_relativas() -> None:
    path = ';.;bin;"C:\\con comillas";\\sin_unidad;C:\\iceman\\bin;'

    assert carpetas_path(path, windows=True) == [Path("C:/con comillas"), Path("C:/iceman/bin")]


def test_un_cliente_en_el_directorio_actual_nunca_se_usa() -> None:
    relativo = Path(".") / "proxmark3.exe"
    sistema = SistemaSimulado({relativo})

    resultado = _buscar(sistema, path=".;")

    assert resultado.ubicacion is None
    assert relativo not in sistema.consultas


# ---------------------------------------------------------------- Linux / Mac


def test_linux_busca_proxmark3_sin_exe_y_sin_proxspace() -> None:
    home = Path("/home/ana")
    en_path = Path("/usr/local/bin/proxmark3")
    sistema = SistemaSimulado({en_path, Path("C:/ProxSpace/pm3/proxmark3/client/proxmark3.exe")})

    ubicacion = _buscar(
        sistema, path="/usr/bin:relativo:/usr/local/bin", windows=False, home=home,
        incluido=Path("/opt/pm3-dashboard/pm3-client/proxmark3"),
    ).ubicacion

    assert ubicacion is not None and ubicacion.ruta == en_path
    assert not any("ProxSpace" in str(r) for r in sistema.consultas)
    assert all(not str(r).endswith(".exe") for r in sistema.consultas)


def test_linux_carpeta_del_usuario() -> None:
    home = Path("/home/ana")
    compilado = home / "proxmark3" / "client" / "proxmark3"

    ubicacion = _buscar(SistemaSimulado({compilado}), path="/usr/bin", windows=False, home=home).ubicacion

    assert ubicacion is not None and ubicacion.ruta == compilado


def test_path_linux() -> None:
    assert carpetas_path("/usr/bin::./x:/opt/pm3", windows=False) == [Path("/usr/bin"), Path("/opt/pm3")]
