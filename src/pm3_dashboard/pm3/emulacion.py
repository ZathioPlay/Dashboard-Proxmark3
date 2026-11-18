"""Emulación de tarjetas: un proceso del cliente que sigue abierto hasta que se detiene."""

from __future__ import annotations

import re
import threading
import time

from pm3_dashboard.pm3.cliente import ClientePm3, ErrorPm3, SesionProceso
from pm3_dashboard.pm3.modelos import EstadoEmulacion, Respuesta

PATRON_SIMULACION = re.compile(r"^(hf|lf)\s.+\bsim\b")
# Con -c, el cliente ejecuta varios comandos separados por ';'. Se prohíben
# para que no se pueda colar un comando de escritura detrás de un 'sim'.
CARACTERES_PROHIBIDOS = (";", "\n", "\r")

MSG_YA_ACTIVA = "Ya hay una emulación en curso."
MSG_NINGUNA = "No había ninguna emulación activa."


def validar_comando_emulacion(comando: str) -> str | None:
    """Devuelve el mensaje de error, o None si el comando es válido."""
    if any(caracter in comando for caracter in CARACTERES_PROHIBIDOS):
        return "El comando de emulación no puede contener ';' ni saltos de línea."
    if not PATRON_SIMULACION.match(comando):
        return "Solo se pueden lanzar comandos de simulación (hf ... sim / lf ... sim)."
    return None


class GestorEmulacion:
    """Inicia, consulta y detiene la emulación (una como máximo)."""

    def __init__(self, cliente: ClientePm3, espera_inicial: float = 1.5) -> None:
        self._cliente = cliente
        self._espera_inicial = espera_inicial  # para que el cliente imprima las primeras líneas
        self._mutex = threading.Lock()
        self._sesion: SesionProceso | None = None
        self._comando: str | None = None

    def iniciar(self, comando: str) -> Respuesta[EstadoEmulacion]:
        comando = (comando or "").strip()
        error = validar_comando_emulacion(comando)
        if error:
            return Respuesta(ok=False, error=error)

        with self._mutex:
            if self._sesion is not None and not self._sesion.terminada:
                return Respuesta(ok=False, error=MSG_YA_ACTIVA)
            try:
                sesion = self._cliente.abrir_sesion(comando)
            except ErrorPm3 as exc:
                return Respuesta(ok=False, error=str(exc))
            self._sesion, self._comando = sesion, comando

        time.sleep(self._espera_inicial)
        estado = self.estado()
        return Respuesta(ok=True, datos=estado, salida=estado.salida, puerto=sesion.puerto)

    def estado(self) -> EstadoEmulacion:
        """Si el proceso terminó solo, aparece como no activa (y el puerto ya está libre)."""
        sesion, comando = self._sesion, self._comando
        if sesion is None:
            return EstadoEmulacion(activa=False)
        return EstadoEmulacion(activa=not sesion.terminada, comando=comando, salida=sesion.salida())

    def detener(self) -> Respuesta[EstadoEmulacion]:
        with self._mutex:
            sesion = self._sesion
            self._sesion, self._comando = None, None
        if sesion is None:
            return Respuesta(ok=True, datos=EstadoEmulacion(activa=False), salida=MSG_NINGUNA)

        sesion.detener()
        # Por si el firmware sigue simulando por su cuenta, se le manda parar.
        parada = self._cliente.ejecutar("hw break", timeout=10)
        return Respuesta(
            ok=True,
            datos=EstadoEmulacion(activa=False),
            salida=sesion.salida() + parada.salida,
            puerto=sesion.puerto,
        )
