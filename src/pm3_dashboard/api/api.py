"""Clase expuesta a JavaScript como window.pywebview.api.

- Cada método público se puede llamar desde la interfaz. pywebview lo ejecuta
  en un hilo propio, así que las operaciones lentas no congelan la ventana.
- Devuelven siempre datos serializables a JSON y nunca lanzan excepciones:
  los errores vuelven como {"ok": False, "error": "..."}.
- Las dependencias van en atributos privados (con "_"): pywebview expone a
  JavaScript todos los atributos públicos, también los objetos anidados.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import date
from typing import Any

from pm3_dashboard import paths
from pm3_dashboard.api import conversion
from pm3_dashboard.api.dialogos import Dialogos, DialogosPywebview
from pm3_dashboard.pm3 import Proxmark3
from pm3_dashboard.pm3.cliente import MSG_EMULACION, MSG_OCUPADA
from pm3_dashboard.pm3.modelos import Banda, Respuesta, TarjetaLeida
from pm3_dashboard.storage import BaseDatos, DatosNoValidos, ErrorBaseDatos
from pm3_dashboard.storage import actividad, antenas, intercambio, tarjetas
from pm3_dashboard.storage.actividad import TipoActividad
from pm3_dashboard.storage.intercambio import ErrorImportacion
from pm3_dashboard.storage.tarjetas import NuevaTarjeta

logger = logging.getLogger(__name__)

EVENTOS_RECIENTES = 8
MENSAJES_OCUPADA = (MSG_OCUPADA, MSG_EMULACION)


class ErrorEntrada(ValueError):
    """Un parámetro recibido desde JavaScript no tiene el tipo esperado."""


def _texto(valor: object, campo: str) -> str:
    if not isinstance(valor, str):
        raise ErrorEntrada(f"El campo '{campo}' debe ser texto.")
    return valor


def _entero(valor: object, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorEntrada(f"El campo '{campo}' debe ser un número entero.")
    return valor


def _etiqueta_uid(banda: str) -> str:
    return "ID" if banda == Banda.LF else "UID"


def _cantidad(n: int, participio: str) -> str:
    """(1, 'importada') -> '1 tarjeta importada'; (3, 'importada') -> '3 tarjetas importadas'."""
    plural = "" if n == 1 else "s"
    return f"{n} tarjeta{plural} {participio}{plural}"


class Api:
    """Puente entre la interfaz y la lógica de la aplicación."""

    def __init__(
        self,
        proxmark: Proxmark3 | None = None,
        bd: BaseDatos | None = None,
        dialogos: Dialogos | None = None,
        hoy: Callable[[], date] = date.today,
    ) -> None:
        self._proxmark = proxmark or Proxmark3()
        self._bd = bd or BaseDatos(paths.ruta_bd())
        self._dialogos: Dialogos = dialogos or DialogosPywebview()
        self._hoy = hoy
        # Estado del dispositivo (fase 3)
        self._mutex = threading.Lock()
        self._estado: dict[str, Any] | None = None
        self._conectado: bool | None = None
        self._presente: bool | None = None
        # Última lectura: el servidor la guarda para que la interfaz solo envíe nombre y notas.
        self._mutex_lectura = threading.Lock()
        self._lectura: TarjetaLeida | None = None
        self._id_lectura = 0

    # ================================================================ inicio
    def obtener_resumen(self) -> dict[str, Any]:
        """Datos de la base de datos para la pantalla de inicio (rápido, no usa la Proxmark)."""
        return self._seguro(self._resumen)

    def obtener_estado_dispositivo(self) -> dict[str, Any]:
        """Estado de la Proxmark3 con 'hw version' (puede tardar unos segundos)."""
        return self._seguro(self._estado_dispositivo)

    def comprobar_conexion(self) -> dict[str, Any]:
        """Comprobación ligera y periódica: solo mira si el puerto existe.

        'cambio' es "aparece", "desaparece" o None. Al desaparecer se incluye
        el nuevo 'estado'; al aparecer, la interfaz debe pedir el estado completo.
        """
        return self._seguro(self._conexion)

    def medir_antenas(self) -> dict[str, Any]:
        """Lanza 'hw tune' (hasta 45 s), guarda la medición y la registra en la actividad."""
        return self._seguro(self._medir_antenas)

    # ================================================================ lectura
    def escanear(self, banda: str = "auto") -> dict[str, Any]:
        """Busca una tarjeta (auto, hf o lf). Puede tardar hasta ~30 s."""
        return self._seguro(lambda: self._escanear(banda))

    def guardar_tarjeta(self, id_lectura: int, nombre: str, notas: str = "") -> dict[str, Any]:
        """Guarda la última lectura. La interfaz solo aporta el nombre y las notas."""
        return self._seguro(lambda: self._guardar_tarjeta(id_lectura, nombre, notas))

    # ================================================================ base de datos
    def listar_tarjetas(self, texto: str = "", banda: str = "") -> dict[str, Any]:
        return self._seguro(lambda: self._listar(texto, banda))

    def obtener_tarjeta(self, id_tarjeta: int) -> dict[str, Any]:
        return self._seguro(lambda: self._obtener(id_tarjeta))

    def editar_tarjeta(self, id_tarjeta: int, nombre: str, notas: str = "") -> dict[str, Any]:
        return self._seguro(lambda: self._editar(id_tarjeta, nombre, notas))

    def borrar_tarjeta(self, id_tarjeta: int) -> dict[str, Any]:
        """Borra la tarjeta (la interfaz pide confirmación antes)."""
        return self._seguro(lambda: self._borrar(id_tarjeta))

    def exportar_tarjetas(self) -> dict[str, Any]:
        """Abre el diálogo de guardar y exporta todas las tarjetas a JSON."""
        return self._seguro(self._exportar)

    def importar_tarjetas(self) -> dict[str, Any]:
        """Abre el diálogo de abrir e importa las tarjetas válidas del JSON."""
        return self._seguro(self._importar)

    # ================================================================ implementación
    def _seguro(self, operacion: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return operacion()
        except (DatosNoValidos, ErrorImportacion, ErrorEntrada) as exc:
            return {"ok": False, "error": str(exc)}
        except ErrorBaseDatos as exc:
            logger.exception("Error de base de datos")
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            logger.exception("Error inesperado en la Api")
            return {"ok": False, "error": f"Error inesperado: {exc}"}

    # ---------------------------------------------------------------- inicio
    def _resumen(self) -> dict[str, Any]:
        return {
            "ok": True,
            "tarjetas": tarjetas.contar_por_banda(self._bd),
            "antenas": conversion.medicion(antenas.ultima_medicion(self._bd)),
            "actividad": [
                {"fecha": e.fecha, "tipo": e.tipo, "descripcion": e.descripcion}
                for e in actividad.ultimas(self._bd, EVENTOS_RECIENTES)
            ],
        }

    def _estado_dispositivo(self) -> dict[str, Any]:
        # Línea base para la comprobación periódica.
        self._actualizar_presencia(self._presencia())

        respuesta = self._proxmark.estado()
        if not respuesta.ok and respuesta.error in MENSAJES_OCUPADA:
            # Ocupada (midiendo, emulando...) significa conectada: se mantiene lo último conocido.
            anterior = self._estado or {
                **conversion.estado(Respuesta(ok=True)),
                "puerto": respuesta.puerto,
                "cliente_iceman": conversion.cliente_iceman(self._proxmark.buscar_cliente()),
            }
            return {"ok": True, **anterior, "ocupado": True}

        estado = conversion.estado(respuesta)
        # Qué cliente se usa y de dónde sale, también sin Proxmark conectada.
        version = conversion.version_corta(respuesta.datos.cliente) if respuesta.datos else ""
        estado["cliente_iceman"] = conversion.cliente_iceman(self._proxmark.buscar_cliente(), version)
        self._guardar_estado(estado)
        return {"ok": True, **estado}

    def _conexion(self) -> dict[str, Any]:
        puerto = self._presencia()
        presente = puerto is not None
        anterior = self._actualizar_presencia(presente)

        cambio = None
        if anterior is not None and anterior != presente:
            cambio = "aparece" if presente else "desaparece"

        estado = None
        if cambio == "desaparece":
            estado = conversion.estado_desconectado("Se ha desconectado la Proxmark3. Vuelve a conectarla por USB.")
            # El cliente sigue siendo el mismo: se conserva su versión conocida.
            anterior = (self._estado or {}).get("cliente_iceman") or {}
            estado["cliente_iceman"] = conversion.cliente_iceman(
                self._proxmark.buscar_cliente(), anterior.get("version", "")
            )
            self._guardar_estado(estado)
        return {"ok": True, "presente": presente, "puerto": puerto, "cambio": cambio, "estado": estado}

    def _medir_antenas(self) -> dict[str, Any]:
        respuesta = self._proxmark.medir_antenas()
        if not respuesta.ok or respuesta.datos is None:
            return {"ok": False, "error": respuesta.error or "No se pudo medir las antenas."}

        guardada = antenas.guardar_medicion(self._bd, respuesta.datos)
        actividad.registrar(
            self._bd,
            TipoActividad.ANTENAS,
            f"Medición de antenas: LF {conversion.voltios_texto(respuesta.datos.lf)}, "
            f"HF {conversion.voltios_texto(respuesta.datos.hf)}",
        )
        return {"ok": True, "medicion": conversion.medicion(guardada)}

    # ---------------------------------------------------------------- lectura
    def _escanear(self, banda: object) -> dict[str, Any]:
        respuesta = self._proxmark.escanear(_texto(banda, "banda"))
        if not respuesta.ok or respuesta.datos is None:
            return {"ok": False, "error": respuesta.error, "salida": respuesta.salida}

        lectura = respuesta.datos
        with self._mutex_lectura:
            self._id_lectura += 1
            id_lectura = self._id_lectura
            self._lectura = lectura

        actividad.registrar(
            self._bd,
            TipoActividad.LECTURA,
            f"Leída {lectura.tipo.value} ({_etiqueta_uid(lectura.banda)} {lectura.uid})",
        )
        guardadas = tarjetas.nombres_con_uid(self._bd, lectura.uid)
        return {"ok": True, "tarjeta": conversion.tarjeta_leida(lectura, id_lectura, guardadas)}

    def _guardar_tarjeta(self, id_lectura: object, nombre: object, notas: object) -> dict[str, Any]:
        id_lectura = _entero(id_lectura, "id_lectura")
        nombre, notas = _texto(nombre, "nombre"), _texto(notas, "notas")

        # Todo bajo el cerrojo: comprobar, guardar y olvidar la lectura. Así un
        # escaneo simultáneo o un doble clic no guardan otra lectura ni duplican.
        with self._mutex_lectura:
            lectura = self._lectura
            if lectura is None or id_lectura != self._id_lectura:
                return {
                    "ok": False,
                    "error": "La lectura ya no está disponible (se ha guardado o se ha vuelto a escanear). "
                    "Escanea la tarjeta de nuevo.",
                }
            nueva = NuevaTarjeta(
                nombre=nombre,
                notas=notas,
                fecha=lectura.fecha,
                banda=lectura.banda.value,
                tipo=lectura.tipo.value,
                uid=lectura.uid,
                atqa=lectura.atqa,
                sak=lectura.sak,
                salida=lectura.salida,
            )
            id_tarjeta = tarjetas.insertar_tarjeta(self._bd, nueva)
            self._lectura = None

        actividad.registrar(
            self._bd,
            TipoActividad.GUARDADO,
            f"Guardada «{nueva.nombre.strip()}» ({nueva.tipo}, {_etiqueta_uid(nueva.banda)} {lectura.uid})",
        )
        return {"ok": True, "id": id_tarjeta}

    # ---------------------------------------------------------------- base de datos
    def _listar(self, texto: object, banda: object) -> dict[str, Any]:
        lista = tarjetas.listar(self._bd, _texto(texto, "texto"), _texto(banda, "banda"))
        return {"ok": True, "tarjetas": [conversion.tarjeta_guardada(t) for t in lista]}

    def _obtener(self, id_tarjeta: object) -> dict[str, Any]:
        tarjeta = tarjetas.obtener(self._bd, _entero(id_tarjeta, "id"))
        if tarjeta is None:
            return {"ok": False, "error": "La tarjeta no existe (puede que se haya borrado)."}
        return {"ok": True, "tarjeta": conversion.tarjeta_guardada(tarjeta)}

    def _editar(self, id_tarjeta: object, nombre: object, notas: object) -> dict[str, Any]:
        encontrada = tarjetas.actualizar(
            self._bd, _entero(id_tarjeta, "id"), _texto(nombre, "nombre"), _texto(notas, "notas")
        )
        if not encontrada:
            return {"ok": False, "error": "La tarjeta no existe (puede que se haya borrado)."}
        return {"ok": True}

    def _borrar(self, id_tarjeta: object) -> dict[str, Any]:
        id_tarjeta = _entero(id_tarjeta, "id")
        tarjeta = tarjetas.obtener(self._bd, id_tarjeta)
        if tarjeta is None or not tarjetas.borrar(self._bd, id_tarjeta):
            return {"ok": False, "error": "La tarjeta no existe (puede que ya se haya borrado)."}
        actividad.registrar(
            self._bd, TipoActividad.BORRADO, f"Borrada «{tarjeta.nombre}» ({tarjeta.tipo}, {tarjeta.uid})"
        )
        return {"ok": True}

    def _exportar(self) -> dict[str, Any]:
        ruta = self._dialogos.elegir_guardar(f"tarjetas_{self._hoy().isoformat()}.json")
        if ruta is None:
            return {"ok": False, "cancelado": True}
        texto, cantidad = intercambio.exportar_json(self._bd)
        try:
            ruta.write_text(texto, encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"No se pudo escribir {ruta}: {exc}"}
        actividad.registrar(self._bd, TipoActividad.EXPORTACION, f"{_cantidad(cantidad, 'exportada')} a {ruta.name}")
        return {"ok": True, "cantidad": cantidad, "ruta": str(ruta)}

    def _importar(self) -> dict[str, Any]:
        ruta = self._dialogos.elegir_abrir()
        if ruta is None:
            return {"ok": False, "cancelado": True}
        try:
            if ruta.stat().st_size > intercambio.MAX_BYTES:
                raise ErrorImportacion(
                    f"El archivo supera el máximo de {intercambio.MAX_BYTES // (1024 * 1024)} MB."
                )
            texto = ruta.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return {"ok": False, "error": "El archivo no es texto UTF-8."}
        except OSError as exc:
            return {"ok": False, "error": f"No se pudo leer {ruta}: {exc}"}

        resultado = intercambio.importar_json(self._bd, texto)
        descripcion = f"{_cantidad(resultado.importadas, 'importada')} desde {ruta.name}"
        if resultado.rechazadas:
            rechazadas = len(resultado.rechazadas)
            descripcion += f" ({rechazadas} rechazada{'' if rechazadas == 1 else 's'})"
        actividad.registrar(self._bd, TipoActividad.IMPORTACION, descripcion)
        return conversion.resultado_importacion(resultado, ruta.name)

    # ---------------------------------------------------------------- estado interno
    def _presencia(self) -> str | None:
        try:
            return self._proxmark.puerto_presente()
        except Exception:
            logger.exception("Error al comprobar la presencia de la Proxmark3")
            return None

    def _actualizar_presencia(self, presente: bool | str | None) -> bool | None:
        """Guarda la presencia actual y devuelve la anterior."""
        with self._mutex:
            anterior, self._presente = self._presente, bool(presente)
        return anterior

    def _guardar_estado(self, estado: dict[str, Any]) -> None:
        """Guarda el estado y registra en la actividad los cambios de conexión."""
        with self._mutex:
            anterior, self._conectado = self._conectado, estado["conectado"]
            self._estado = estado
        # Al arrancar sin Proxmark no se registra nada (sería ruido en cada inicio).
        if anterior == estado["conectado"] or (anterior is None and not estado["conectado"]):
            return
        if estado["conectado"]:
            descripcion = f"Proxmark3 conectada en {estado['puerto']}"
            if estado["version_firmware"]:
                descripcion += f" (firmware {estado['version_firmware']})"
        else:
            descripcion = "Proxmark3 desconectada"
        actividad.registrar(self._bd, TipoActividad.CONEXION, descripcion)
