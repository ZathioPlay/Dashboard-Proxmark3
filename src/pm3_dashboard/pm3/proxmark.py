"""Fachada del paquete pm3: las operaciones que usará la Api (fase 3)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from pm3_dashboard.pm3.cliente import ClientePm3
from pm3_dashboard.pm3.emulacion import GestorEmulacion
from pm3_dashboard.pm3.localizador import ResultadoBusqueda
from pm3_dashboard.pm3.modelos import (
    EstadoEmulacion,
    InfoVersion,
    MedicionAntenas,
    Respuesta,
    ResultadoComando,
    TarjetaLeida,
    TipoTarjeta,
    Volcado,
)
from pm3_dashboard.pm3.parsers import (
    parsear_hf_search,
    parsear_hw_tune,
    parsear_hw_version,
    parsear_lf_search,
    parsear_volcado,
)
from pm3_dashboard.pm3.recetas import receta_hf, receta_lf

BANDAS = ("auto", "hf", "lf")
MSG_SIN_TARJETA = "No se detectó ninguna tarjeta sobre la antena de Proxmark3."
MSG_SOLO_HF = "Solo se puede volcar la memoria de tarjetas HF."

TIMEOUT_VOLCADO = 60.0
# autopwn prueba miles de claves; en el peor caso tarda varios minutos.
TIMEOUT_AUTOPWN = 600.0

_COMANDO_DUMP = {
    TipoTarjeta.MIFARE_CLASSIC_1K: "hf mf dump",
    TipoTarjeta.MIFARE_CLASSIC_4K: "hf mf dump",
    TipoTarjeta.ULTRALIGHT_NTAG: "hf mfu dump",
}


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

    def buscar_cliente(self) -> ResultadoBusqueda:
        """Qué cliente de Iceman se usa y de dónde sale (no ejecuta nada)."""
        return self.cliente.buscar_cliente()

    def puerto_presente(self) -> str | None:
        """Comprobación ligera de conexión (no lanza 'hw version')."""
        return self.cliente.puerto_presente()

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

    def leer_bloques(self, tipo: str, uid: str) -> Respuesta[Volcado]:
        """Vuelca la memoria de una tarjeta HF con las claves por defecto (no intenta autopwn)."""
        tipo_tarjeta = TipoTarjeta(tipo)
        comando = _COMANDO_DUMP.get(tipo_tarjeta)
        if comando is None:
            return Respuesta(ok=False, error=MSG_SOLO_HF)
        res = self.cliente.ejecutar(comando, timeout=TIMEOUT_VOLCADO)
        if not res.ok:
            return Respuesta(ok=False, error=res.error, salida=res.salida, puerto=res.puerto)
        return Respuesta(ok=True, datos=parsear_volcado(res.salida, tipo_tarjeta), salida=res.salida, puerto=res.puerto)

    def recuperar_claves(self, uid: str, tipo: str = TipoTarjeta.MIFARE_CLASSIC_1K) -> Respuesta[Volcado]:
        """Recupera las claves de una MIFARE Classic con 'hf mf autopwn'. Operación larga."""
        tipo_tarjeta = TipoTarjeta(tipo)
        if tipo_tarjeta not in (TipoTarjeta.MIFARE_CLASSIC_1K, TipoTarjeta.MIFARE_CLASSIC_4K):
            return Respuesta(ok=False, error="La recuperación de claves solo se aplica a MIFARE Classic.")
        res = self.cliente.ejecutar("hf mf autopwn", timeout=TIMEOUT_AUTOPWN)
        if not res.ok:
            return Respuesta(ok=False, error=res.error, salida=res.salida, puerto=res.puerto)
        return Respuesta(ok=True, datos=parsear_volcado(res.salida, tipo_tarjeta), salida=res.salida, puerto=res.puerto)

    def ejecutar(self, comando: str, timeout: float = 15.0) -> ResultadoComando:
        """Comando libre (clonado generado por recetas.py, futura terminal)."""
        return self.cliente.ejecutar(comando, timeout=timeout)

    def iniciar_emulacion(self, comando: str) -> Respuesta[EstadoEmulacion]:
        return self.emulacion.iniciar(comando)

    def detener_emulacion(self) -> Respuesta[EstadoEmulacion]:
        return self.emulacion.detener()

    def estado_emulacion(self) -> EstadoEmulacion:
        return self.emulacion.estado()
