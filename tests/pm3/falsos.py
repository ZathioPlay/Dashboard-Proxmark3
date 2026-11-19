"""Dobles de prueba: un cliente de Iceman falso para no usar nunca la Proxmark real."""

from __future__ import annotations

import queue
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from pm3_dashboard.pm3.cliente import SalidaProceso

CARPETA_MUESTRAS = Path(__file__).parent / "muestras"


def cargar_muestra(nombre: str) -> str:
    """Salida de ejemplo del cliente de Iceman (tests/pm3/muestras/<nombre>.txt)."""
    return (CARPETA_MUESTRAS / f"{nombre}.txt").read_text(encoding="utf-8")


def esperar_hasta(condicion: Callable[[], bool], limite: float = 2.0) -> bool:
    """Espera activa corta para condiciones que cambian en otro hilo."""
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(0.01)
    return condicion()


class FlujoFalso:
    """Imita proceso.stdout: readline() espera hasta que hay una línea o se cierra."""

    def __init__(self) -> None:
        self._cola: queue.Queue[str | None] = queue.Queue()

    def escribir(self, linea: str) -> None:
        self._cola.put(linea)

    def cerrar(self) -> None:
        self._cola.put(None)

    def readline(self) -> str:
        linea = self._cola.get()
        if linea is None:
            self._cola.put(None)  # sigue cerrado para siguientes lecturas
            return ""
        return linea


class ProcesoFalso:
    """Imita un subprocess.Popen de emulación que no termina hasta que se le detiene."""

    def __init__(self, lineas: Sequence[str] = (), ignora_terminate: bool = False) -> None:
        self.stdout = FlujoFalso()
        for linea in lineas:
            self.stdout.escribir(linea)
        self.returncode: int | None = None
        self.ignora_terminate = ignora_terminate
        self.terminate_llamado = False
        self.kill_llamado = False
        self._fin = threading.Event()

    def poll(self) -> int | None:
        return self.returncode

    def terminar_solo(self, codigo: int = 0) -> None:
        """Simula que el proceso termina por su cuenta (error, botón de la PM3...)."""
        self._finalizar(codigo)

    def terminate(self) -> None:
        self.terminate_llamado = True
        if not self.ignora_terminate:
            self._finalizar(1)

    def kill(self) -> None:
        self.kill_llamado = True
        self._finalizar(-9)

    def wait(self, timeout: float | None = None) -> int:
        if not self._fin.wait(timeout):
            raise subprocess.TimeoutExpired("proxmark3", timeout or 0)
        assert self.returncode is not None
        return self.returncode

    def _finalizar(self, codigo: int) -> None:
        if self.returncode is None:
            self.returncode = codigo
            self.stdout.cerrar()
            self._fin.set()


class LanzadorFalso:
    """Lanzador que responde con salidas preparadas y apunta cada llamada."""

    def __init__(self) -> None:
        self.respuestas: dict[str, SalidaProceso | BaseException] = {}
        self.llamadas: list[list[str]] = []
        self.timeouts: list[float] = []
        self.procesos: list[ProcesoFalso] = []
        self.consolas: list[dict] = []
        self.lineas_emulacion: list[str] = ["[=] Press pm3 button to abort simulation\n"]
        self.ignora_terminate = False
        self.error_al_abrir: OSError | None = None
        # Para simular un comando lento: ejecutar() espera a que se active.
        self.bloqueo: threading.Event | None = None
        self.dentro = threading.Event()

    def responder(self, comando: str, stdout: str = "", codigo: int = 0, stderr: str = "") -> None:
        self.respuestas[comando] = SalidaProceso(codigo, stdout, stderr)

    def fallar(self, comando: str, error: BaseException) -> None:
        self.respuestas[comando] = error

    @property
    def comandos(self) -> list[str]:
        """Comando (-c) de cada llamada, en orden."""
        return [argv[-1] for argv in self.llamadas]

    def ejecutar(
        self, argv: Sequence[str], *, timeout: float, env: Mapping[str, str], cwd: Path
    ) -> SalidaProceso:
        self.llamadas.append(list(argv))
        self.timeouts.append(timeout)
        self.dentro.set()
        if self.bloqueo is not None:
            self.bloqueo.wait(5)
        respuesta = self.respuestas.get(argv[-1], SalidaProceso(0, "", ""))
        if isinstance(respuesta, BaseException):
            raise respuesta
        return respuesta

    def abrir(self, argv: Sequence[str], *, env: Mapping[str, str], cwd: Path) -> ProcesoFalso:
        self.llamadas.append(list(argv))
        if self.error_al_abrir is not None:
            raise self.error_al_abrir
        proceso = ProcesoFalso(self.lineas_emulacion, ignora_terminate=self.ignora_terminate)
        self.procesos.append(proceso)
        return proceso

    def lanzar_consola(self, argv: Sequence[str], *, env: Mapping[str, str], cwd: Path) -> None:
        # No abre nada: solo registra el comando y el entorno para los tests.
        self.consolas.append({"argv": list(argv), "env": dict(env), "cwd": cwd})
