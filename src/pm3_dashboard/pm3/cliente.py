"""Ejecución del cliente de Iceman (proxmark3.exe) con acceso exclusivo al puerto.

El puerto COM solo admite un cliente a la vez, así que ClientePm3 tiene un
cerrojo: un comando normal lo toma mientras dura, y una sesión larga
(emulación) lo mantiene hasta que se detiene o el proceso termina.

El acceso a subprocess pasa por un Lanzador para poder sustituirlo en los
tests por uno falso y no usar nunca la Proxmark real.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Protocol

from pm3_dashboard import paths
from pm3_dashboard.config import ConfigPm3, cargar_config, resolver_ruta_cliente, resolver_rutas_extra
from pm3_dashboard.pm3.modelos import ResultadoComando
from pm3_dashboard.pm3.puerto import detectar_puerto, puerto_presente
from pm3_dashboard.pm3.salida import interpretar_salida, limpiar_salida

MAX_LINEAS_SESION = 500
ESPERA_PARADA_S = 3.0

MSG_OCUPADA = "La Proxmark3 está ocupada con otro comando."
MSG_EMULACION = "Hay una emulación en curso. Detenla antes de lanzar otro comando."
MSG_TIEMPO_AGOTADO = "Tiempo de espera agotado al comunicar con Proxmark3."


class ErrorPm3(Exception):
    """Error al preparar o lanzar el cliente (el mensaje se muestra al usuario)."""


class TiempoAgotado(Exception):
    """El comando no terminó dentro del tiempo límite."""


# ---------------------------------------------------------------------------
# Lanzador: única parte que usa subprocess
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SalidaProceso:
    codigo: int
    stdout: str
    stderr: str


class ProcesoLargo(Protocol):
    """Lo que se usa de subprocess.Popen."""

    stdout: IO[str] | None

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


class Lanzador(Protocol):
    def ejecutar(
        self, argv: Sequence[str], *, timeout: float, env: Mapping[str, str], cwd: Path
    ) -> SalidaProceso: ...

    def abrir(self, argv: Sequence[str], *, env: Mapping[str, str], cwd: Path) -> ProcesoLargo: ...


def _sin_ventana() -> int:
    """En Windows evita que se abra una consola negra al lanzar el cliente."""
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class LanzadorSubprocess:
    """Lanzador real basado en subprocess."""

    def ejecutar(
        self, argv: Sequence[str], *, timeout: float, env: Mapping[str, str], cwd: Path
    ) -> SalidaProceso:
        try:
            proceso = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=dict(env),
                cwd=str(cwd),
                creationflags=_sin_ventana(),
            )
        except subprocess.TimeoutExpired as exc:
            raise TiempoAgotado from exc
        return SalidaProceso(proceso.returncode, proceso.stdout or "", proceso.stderr or "")

    def abrir(self, argv: Sequence[str], *, env: Mapping[str, str], cwd: Path) -> ProcesoLargo:
        return subprocess.Popen(
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=dict(env),
            cwd=str(cwd),
            creationflags=_sin_ventana(),
        )


# ---------------------------------------------------------------------------
# Preparación (ruta del cliente, puerto y entorno)
# ---------------------------------------------------------------------------
def construir_entorno(
    cliente: Path, rutas_extra: Sequence[Path], base: Mapping[str, str]
) -> dict[str, str]:
    """Variables de entorno para el cliente: PATH con sus DLL y las carpetas extra."""
    env = dict(base)
    extras = [str(cliente.parent)]

    # El cliente precompilado para Windows lleva sus DLL en libs/, igual que
    # hace su setup.bat al añadirlas al PATH.
    libs = cliente.parent / "libs"
    if libs.is_dir():
        extras += [str(libs), str(libs / "shell")]
        env["QT_PLUGIN_PATH"] = str(libs)
        env["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(libs)

    extras += [str(ruta) for ruta in rutas_extra]
    env["PATH"] = os.pathsep.join(extras + [env.get("PATH", "")])
    return env


@dataclass(frozen=True)
class _Preparacion:
    cliente: Path
    puerto: str
    env: dict[str, str]

    def argv(self, comando: str) -> list[str]:
        return [str(self.cliente), "-p", self.puerto, "-c", comando]


# ---------------------------------------------------------------------------
# Sesión larga (emulación)
# ---------------------------------------------------------------------------
class SesionProceso:
    """Proceso del cliente que sigue abierto (emulación).

    Un hilo va leyendo su salida (últimas MAX_LINEAS_SESION líneas). El puerto
    se libera una sola vez, al detenerla o cuando el proceso termina solo.
    """

    def __init__(self, proceso: ProcesoLargo, puerto: str, al_terminar: Callable[[], None]) -> None:
        self.proceso = proceso
        self.puerto = puerto
        self._al_terminar = al_terminar
        self._lineas: deque[str] = deque(maxlen=MAX_LINEAS_SESION)
        self._mutex = threading.Lock()
        self._liberada = False
        self._hilo = threading.Thread(target=self._leer, name="pm3-sesion", daemon=True)
        self._hilo.start()

    @property
    def terminada(self) -> bool:
        return self._liberada or self.proceso.poll() is not None

    def salida(self) -> str:
        return "".join(list(self._lineas))

    def detener(self, espera: float = ESPERA_PARADA_S) -> None:
        """Termina el proceso (o lo mata si no responde) y libera el puerto."""
        try:
            if self.proceso.poll() is None:
                self.proceso.terminate()
                try:
                    self.proceso.wait(timeout=espera)
                except subprocess.TimeoutExpired:
                    self.proceso.kill()
                    self.proceso.wait(timeout=espera)
        finally:
            self._liberar()
        self._hilo.join(timeout=1)  # recoge las últimas líneas

    def _leer(self) -> None:
        stdout = self.proceso.stdout
        if stdout is not None:
            try:
                for linea in iter(stdout.readline, ""):
                    self._lineas.append(limpiar_salida(linea))
            except (OSError, ValueError):  # tubería cerrada
                pass
        # Fin de la salida: el proceso ha terminado (solo o detenido).
        self._liberar()

    def _liberar(self) -> None:
        with self._mutex:
            if self._liberada:
                return
            self._liberada = True
        self._al_terminar()


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------
class ClientePm3:
    """Lanza comandos del cliente de Iceman, de uno en uno."""

    def __init__(
        self,
        cargar: Callable[[], ConfigPm3] = cargar_config,
        lanzador: Lanzador | None = None,
        detectar: Callable[[str], str | None] = detectar_puerto,
        carpeta_trabajo: Path | None = None,
        presencia: Callable[[str], str | None] = puerto_presente,
    ) -> None:
        # La configuración se lee en cada comando: así se puede cambiar sin reiniciar.
        self._cargar = cargar
        self._lanzador: Lanzador = lanzador or LanzadorSubprocess()
        self._detectar = detectar
        self._presencia = presencia
        self._carpeta_trabajo = carpeta_trabajo
        self._cerrojo = threading.Lock()
        self._sesion: SesionProceso | None = None

    @property
    def emulando(self) -> bool:
        sesion = self._sesion
        return sesion is not None and not sesion.terminada

    def puerto_presente(self) -> str | None:
        """Comprobación ligera: el puerto si la Proxmark3 está conectada, sin lanzar el cliente."""
        return self._presencia(self._cargar().puerto)

    def ejecutar(self, comando: str, timeout: float = 15.0) -> ResultadoComando:
        """Lanza un comando y espera a que termine. Nunca lanza excepciones."""
        if self.emulando:
            return ResultadoComando(ok=False, error=MSG_EMULACION)
        try:
            prep = self._preparar()
        except ErrorPm3 as exc:
            return ResultadoComando(ok=False, error=str(exc))

        if not self._cerrojo.acquire(timeout=timeout):
            return ResultadoComando(ok=False, error=MSG_OCUPADA, puerto=prep.puerto)
        try:
            salida = self._lanzador.ejecutar(
                prep.argv(comando), timeout=timeout, env=prep.env, cwd=self._cwd()
            )
        except TiempoAgotado:
            return ResultadoComando(ok=False, error=MSG_TIEMPO_AGOTADO, puerto=prep.puerto)
        except FileNotFoundError:
            return ResultadoComando(
                ok=False, error=f"No se pudo ejecutar el cliente de Iceman ({prep.cliente}).", puerto=prep.puerto
            )
        except OSError as exc:
            return ResultadoComando(
                ok=False, error=f"Error al lanzar el cliente de Iceman: {exc}", puerto=prep.puerto
            )
        finally:
            self._cerrojo.release()
        return interpretar_salida(salida.codigo, salida.stdout, salida.stderr, prep.puerto)

    def abrir_sesion(self, comando: str, espera_cerrojo: float = 5.0) -> SesionProceso:
        """Lanza un comando que se queda abierto. El puerto queda ocupado hasta que termine.

        Lanza ErrorPm3 si no se puede abrir.
        """
        if self.emulando:
            raise ErrorPm3(MSG_EMULACION)
        prep = self._preparar()
        if not self._cerrojo.acquire(timeout=espera_cerrojo):
            raise ErrorPm3(MSG_OCUPADA)
        try:
            proceso = self._lanzador.abrir(prep.argv(comando), env=prep.env, cwd=self._cwd())
        except OSError as exc:
            self._cerrojo.release()
            raise ErrorPm3(f"Error al lanzar el cliente de Iceman: {exc}") from exc
        self._sesion = SesionProceso(proceso, prep.puerto, al_terminar=self._cerrojo.release)
        return self._sesion

    def _preparar(self) -> _Preparacion:
        config = self._cargar()
        cliente = resolver_ruta_cliente(config)
        if not cliente.is_file():
            raise ErrorPm3(
                f"No se encuentra el cliente de Iceman en {cliente}. "
                "Revisa 'ruta_cliente' en la configuración (config.json)."
            )
        puerto = self._detectar(config.puerto)
        if not puerto:
            raise ErrorPm3(
                "No se detecta ninguna Proxmark3 conectada por USB. "
                "Conéctala o indica el puerto en la configuración (config.json)."
            )
        env = construir_entorno(cliente, resolver_rutas_extra(config), os.environ)
        return _Preparacion(cliente=cliente, puerto=puerto, env=env)

    def _cwd(self) -> Path:
        if self._carpeta_trabajo is None:
            return paths.carpeta_dumps()
        self._carpeta_trabajo.mkdir(parents=True, exist_ok=True)
        return self._carpeta_trabajo
