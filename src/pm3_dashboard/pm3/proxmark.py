"""Fachada del paquete pm3: las operaciones que usará la Api (fase 3)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from pm3_dashboard.pm3.cliente import ClientePm3
from pm3_dashboard.pm3.emulacion import GestorEmulacion
from pm3_dashboard.pm3.modelos import (
    EstadoEmulacion,
    InfoVersion,
    MedicionAntenas,
    Respuesta,
    ResultadoComando,
    TarjetaLeida,
)
from pm3_dashboard.pm3.parsers import (
    parsear_hf_search,
    parsear_hw_tune,
    parsear_hw_version,
    parsear_lf_search,
)
from pm3_dashboard.pm3.recetas import receta_hf, receta_lf

BANDAS = ("auto", "hf", "lf")
MSG_SIN_TARJETA = "No se detectó ninguna tarjeta sobre la antena de Proxmark3."


def _hoy() -> str:
    return date.today().isoformat()


class Proxmark3:
    """Operaciones con la Proxmark3. La app debe usar una única instancia."""

    def __init__(
        self,
        cliente: ClientePm3 | None = None,
        hoy: Callable[[], str] = _hoy,
        espera_emulacion: float = 1.5,
    ) -> None:
        self.cliente = cliente or ClientePm3()
        self.emulacion = GestorEmulacion(self.cliente, espera_inicial=espera_emulacion)
        self._hoy = hoy

    def estado(self) -> Respuesta[InfoVersion]:
        """Comprueba la conexión con 'hw version'."""
        res = self.cliente.ejecutar("hw version", timeout=20)
        return Respuesta(
            ok=res.ok,
            datos=parsear_hw_version(res.salida),
            error=res.error,
            salida=res.salida,
            puerto=res.puerto,
        )

    def medir_antenas(self) -> Respuesta[MedicionAntenas]:
        """Lanza 'hw tune' y extrae el voltaje de las antenas LF y HF."""
        res = self.cliente.ejecutar("hw tune", timeout=45)
        if not res.ok:
            return Respuesta(ok=False, error=res.error, salida=res.salida, puerto=res.puerto)
        return Respuesta(ok=True, datos=parsear_hw_tune(res.salida), salida=res.salida, puerto=res.puerto)

    def escanear(self, banda: str = "auto") -> Respuesta[TarjetaLeida]:
        """Busca una tarjeta en HF y/o LF. En "auto" prueba primero HF y luego LF."""
        if banda not in BANDAS:
            return Respuesta(ok=False, error=f"Banda no válida: {banda!r} (usa auto, hf o lf).")

        if banda in ("auto", "hf"):
            res = self.cliente.ejecutar("hf search")
            if not res.ok and banda == "hf":
                return Respuesta(ok=False, error=res.error or "Error de hardware HF", salida=res.salida)
            tarjeta_hf = parsear_hf_search(res.salida)
            if tarjeta_hf:
                return Respuesta(
                    ok=True, datos=receta_hf(tarjeta_hf, res.salida, self._hoy()), puerto=res.puerto
                )

        if banda in ("auto", "lf"):
            res = self.cliente.ejecutar("lf search")
            if not res.ok:
                return Respuesta(ok=False, error=res.error or "Error de hardware LF", salida=res.salida)
            tarjeta_lf = parsear_lf_search(res.salida)
            if tarjeta_lf:
                return Respuesta(
                    ok=True, datos=receta_lf(tarjeta_lf, res.salida, self._hoy()), puerto=res.puerto
                )

        return Respuesta(ok=False, error=MSG_SIN_TARJETA)

    def ejecutar(self, comando: str, timeout: float = 15.0) -> ResultadoComando:
        """Comando libre (para la futura terminal)."""
        return self.cliente.ejecutar(comando, timeout=timeout)

    def iniciar_emulacion(self, comando: str) -> Respuesta[EstadoEmulacion]:
        return self.emulacion.iniciar(comando)

    def detener_emulacion(self) -> Respuesta[EstadoEmulacion]:
        return self.emulacion.detener()

    def estado_emulacion(self) -> EstadoEmulacion:
        return self.emulacion.estado()
