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
import re
import threading
from collections.abc import Callable
from datetime import date
from typing import Any

from pm3_dashboard import paths
from pm3_dashboard.api import conversion
from pm3_dashboard.api.dialogos import Dialogos, DialogosPywebview
from pm3_dashboard.pm3 import Proxmark3, decodificadores, recetas
from pm3_dashboard.pm3.cliente import MSG_EMULACION, MSG_OCUPADA
from pm3_dashboard.pm3.modelos import Banda, Respuesta, TarjetaLeida, TipoTarjeta, Volcado
from pm3_dashboard.storage import BaseDatos, DatosNoValidos, ErrorBaseDatos
from pm3_dashboard.storage import actividad, antenas, intercambio, tarjetas, volcados
from pm3_dashboard.storage.actividad import TipoActividad
from pm3_dashboard.storage.bd import fecha_texto
from pm3_dashboard.storage.intercambio import ErrorImportacion
from pm3_dashboard.storage.tarjetas import NuevaTarjeta
from pm3_dashboard.pm3.modelos import Tecnologia

logger = logging.getLogger(__name__)

EVENTOS_RECIENTES = 8
MSG_LECTURA_NO_DISPONIBLE = (
    "La lectura ya no está disponible (se ha guardado o se ha vuelto a escanear). "
    "Escanea la tarjeta de nuevo."
)
MENSAJES_OCUPADA = (MSG_OCUPADA, MSG_EMULACION)
TIMEOUT_CLONADO = 120.0
TIMEOUT_TERMINAL = 30.0
MAX_MEDICIONES = 50

# --- Terminal: lista blanca de comandos de lectura/diagnóstico ---------------
# Política por defecto: solo lo que está aquí se ejecuta directo; CUALQUIER otro
# comando pide confirmación (así un comando de escritura nuevo o desconocido
# nunca corre sin confirmar). Ampliar estas listas es seguro.
#
# Un comando es de lectura SOLO si empieza por uno de estos prefijos. No se
# clasifica por la última palabra: "hf mf cload -f dump" o "hf mfu restore -f
# dump" terminan en "dump" pero ESCRIBEN en la tarjeta, así que deben confirmar.
# Si falta algún comando de lectura útil, se añade aquí como prefijo explícito.
PREFIJOS_LECTURA: tuple[str, ...] = (
    "hw version", "hw status", "hw tune", "hw ping", "hw dbg", "hw detectreader",
    "hf search", "lf search", "data", "help", "prefs show",
    "hf mf info", "hf mf chk", "hf mf fchk", "hf mf nested", "hf mf hardnested",
    "hf mf staticnested", "hf mf autopwn", "hf mf rdbl", "hf mf rdsc", "hf mf dump",
    "hf mfu info", "hf mfu rdbl", "hf mfu dump", "hf 14a info", "hf 14a list",
    "hf 14a reader", "hf 14b info", "hf 14b reader", "hf 15 info", "hf 15 reader",
    "hf 15 dump", "hf iclass info", "hf iclass reader", "hf iclass dump",
    "lf t55xx detect", "lf t55xx config", "lf t55xx info", "lf t55xx dump", "lf t55xx trace",
    "lf em 410x reader", "lf em 410x read", "lf hid reader", "lf hid read",
    "lf indala reader", "lf awid reader", "lf search",
)


def _es_comando_lectura(comando_normalizado: str) -> bool:
    return any(
        comando_normalizado == prefijo or comando_normalizado.startswith(prefijo + " ")
        for prefijo in PREFIJOS_LECTURA
    )


def _clasificar_terminal(comando: str) -> str:
    """'vacio' | 'emulacion' | 'lectura' | 'confirmar'."""
    normalizado = " ".join(comando.split()).lower()
    if not normalizado:
        return "vacio"
    if re.search(r"\bsim\b", normalizado):
        return "emulacion"  # la emulación se hace en su sección, no en la terminal
    return "lectura" if _es_comando_lectura(normalizado) else "confirmar"


def _bytes_volcado(volcado: Volcado) -> bytes:
    """Reconstruye la imagen binaria de la tarjeta a partir de los bloques guardados.

    Lanza ValueError si algún bloque no se leyó o no tiene 16 bytes.
    """
    datos = bytearray()
    for sector in volcado.sectores:
        for bloque in sector.bloques:
            hexa = "".join(bloque.datos.split())
            if not bloque.leido or len(hexa) != 32:
                raise ValueError("El volcado está incompleto: no se puede reconstruir la tarjeta.")
            datos += bytes.fromhex(hexa)
    return bytes(datos)


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
        self._volcado_lectura: Volcado | None = None  # bloques leídos del escaneo actual (sin guardar)

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

    def leer_bloques_lectura(self, id_lectura: int) -> dict[str, Any]:
        """Lee la memoria de la tarjeta recién escaneada (sin guardarla).

        Classic usa autopwn (OPERACIÓN LARGA si no tiene claves de fábrica). El
        volcado se asocia a la tarjeta si luego se guarda.
        """
        return self._seguro(lambda: self._leer_bloques_lectura(id_lectura))

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

    # ================================================================ memoria HF (volcado y clonado)
    def leer_bloques(self, id_tarjeta: int) -> dict[str, Any]:
        """Vuelca la memoria de una tarjeta HF guardada y lo guarda.

        En MIFARE Classic usa 'hf mf autopwn' (OPERACIÓN LARGA si no tiene claves
        de fábrica): prueba las claves por defecto y, si hacen falta, las recupera.
        """
        return self._seguro(lambda: self._leer_bloques(id_tarjeta))

    def obtener_volcado(self, id_tarjeta: int) -> dict[str, Any]:
        """Último volcado guardado de la tarjeta (sin leer la Proxmark)."""
        return self._seguro(lambda: self._obtener_volcado(id_tarjeta))

    def clonar_tarjeta(self, id_tarjeta: int) -> dict[str, Any]:
        """Clona a una tarjeta mágica usando el volcado guardado. ESCRITURA (se confirma en la interfaz)."""
        return self._seguro(lambda: self._clonar_tarjeta(id_tarjeta))

    # ================================================================ escritura de bloques (laboratorio)
    def preparar_datos_bloque(self, tecnologia: str, datos: str, es_texto: bool = False) -> dict[str, Any]:
        """Ayuda texto->hex: devuelve el hex final (relleno/truncado) sin escribir nada."""
        return self._seguro(lambda: self._preparar_datos_bloque(tecnologia, datos, es_texto))

    def escribir_bloque(
        self,
        id_tarjeta: int,
        indice: int,
        datos: str,
        es_texto: bool = False,
        clave: str = recetas.CLAVE_POR_DEFECTO,
        usar_clave_b: bool = False,
        modo_experto: bool = False,
        confirmado: bool = False,
    ) -> dict[str, Any]:
        """Escribe un bloque (laboratorio, tarjetas propias). ESCRITURA: valida y confirma en la Api."""
        return self._seguro(
            lambda: self._escribir_bloque(
                id_tarjeta, indice, datos, es_texto, clave, usar_clave_b, modo_experto, confirmado
            )
        )

    def leer_bloque(
        self, id_tarjeta: int, indice: int, clave: str = recetas.CLAVE_POR_DEFECTO, usar_clave_b: bool = False
    ) -> dict[str, Any]:
        """Relee un solo bloque para verificar una escritura."""
        return self._seguro(lambda: self._leer_bloque(id_tarjeta, indice, clave, usar_clave_b))

    # ================================================================ antenas
    def listar_mediciones(self, limite: int = 10) -> dict[str, Any]:
        """Histórico de mediciones de antenas (de la base de datos)."""
        return self._seguro(lambda: self._listar_mediciones(limite))

    # ================================================================ emulación
    def emular_tarjeta(self, id_tarjeta: int) -> dict[str, Any]:
        """Emula una tarjeta guardada con el comando generado por recetas.py. ESCRITURA/RF (se confirma en la interfaz)."""
        return self._seguro(lambda: self._emular_tarjeta(id_tarjeta))

    def detener_emulacion(self) -> dict[str, Any]:
        return self._seguro(self._detener_emulacion)

    def estado_emulacion(self) -> dict[str, Any]:
        """Estado y salida de la emulación en curso (para que la interfaz sondee)."""
        return self._seguro(self._estado_emulacion)

    # ================================================================ terminal
    def ejecutar_terminal(self, comando: str, confirmado: bool = False) -> dict[str, Any]:
        """Ejecuta un comando del cliente. Solo los de lectura/diagnóstico corren directos;
        cualquier otro pide confirmación (comprobado aquí, no solo en la interfaz)."""
        return self._seguro(lambda: self._ejecutar_terminal(comando, confirmado))

    def estado_consola(self) -> dict[str, Any]:
        """Si se puede abrir el cliente en una consola nativa (hay cliente localizado y puerto)."""
        return self._seguro(self._estado_consola)

    def abrir_consola_pm3(self) -> dict[str, Any]:
        """Abre el cliente de Iceman en una consola de PowerShell propia. No bloquea la app."""
        return self._seguro(self._abrir_consola)

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
            self._volcado_lectura = None  # un escaneo nuevo descarta el volcado anterior

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
                return {"ok": False, "error": MSG_LECTURA_NO_DISPONIBLE}
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
            volcado_pendiente = self._volcado_lectura
            self._lectura = None
            self._volcado_lectura = None

        # Si ya se habían leído los bloques de este escaneo, se asocian a la tarjeta.
        if volcado_pendiente is not None:
            volcados.guardar_volcado(self._bd, id_tarjeta, volcado_pendiente)

        actividad.registrar(
            self._bd,
            TipoActividad.GUARDADO,
            f"Guardada «{nueva.nombre.strip()}» ({nueva.tipo}, {_etiqueta_uid(nueva.banda)} {lectura.uid})",
        )
        return {"ok": True, "id": id_tarjeta}

    def _leer_bloques_lectura(self, id_lectura: object) -> dict[str, Any]:
        id_lectura = _entero(id_lectura, "id_lectura")
        # Se capturan tipo/UID bajo el cerrojo y se suelta: autopwn puede tardar
        # minutos y no debe bloquear ni guardar ni un nuevo escaneo.
        with self._mutex_lectura:
            lectura = self._lectura
            if lectura is None or id_lectura != self._id_lectura:
                return {"ok": False, "error": MSG_LECTURA_NO_DISPONIBLE}
        if lectura.banda == Banda.LF:
            return {"ok": False, "error": "Solo se pueden leer los bloques de tarjetas HF."}

        respuesta = self._proxmark.leer_bloques(lectura.tipo, lectura.uid)
        if not respuesta.ok or respuesta.datos is None:
            return {"ok": False, "error": respuesta.error or "No se pudo leer la memoria.", "salida": respuesta.salida}

        datos = respuesta.datos
        # Solo se asocia si no se ha vuelto a escanear mientras tanto.
        with self._mutex_lectura:
            if id_lectura == self._id_lectura:
                self._volcado_lectura = datos
        actividad.registrar(
            self._bd,
            TipoActividad.LECTURA,
            f"Leídos {datos.bloques_leidos}/{datos.total_bloques} bloques ({_etiqueta_uid(lectura.banda)} {lectura.uid})",
        )
        return {"ok": True, "volcado": conversion.volcado_bruto(datos, fecha_texto())}

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

    # ---------------------------------------------------------------- memoria HF
    def _tarjeta_hf(self, id_tarjeta: object) -> tarjetas.TarjetaGuardada:
        tarjeta = tarjetas.obtener(self._bd, _entero(id_tarjeta, "id"))
        if tarjeta is None:
            raise ErrorEntrada("La tarjeta no existe (puede que se haya borrado).")
        if tarjeta.banda == Banda.LF:
            raise ErrorEntrada("Solo se puede volcar o clonar la memoria de tarjetas HF.")
        return tarjeta

    def _guardar_volcado(self, tarjeta: tarjetas.TarjetaGuardada, respuesta: Respuesta[Volcado]) -> dict[str, Any]:
        volcado = respuesta.datos
        if not respuesta.ok or volcado is None:
            return {"ok": False, "error": respuesta.error or "No se pudo volcar la memoria.", "salida": respuesta.salida}
        guardado = volcados.guardar_volcado(self._bd, tarjeta.id, volcado, salida=respuesta.salida)
        resultado = {"ok": True, "volcado": conversion.volcado(guardado)}

        uid_leido = volcado.uid
        uid_guardado = tarjeta.uid.replace(" ", "").upper()
        if uid_leido and uid_guardado and uid_leido != uid_guardado:
            resultado["aviso"] = (
                f"El UID leído ({uid_leido}) no coincide con el de la tarjeta guardada "
                f"({uid_guardado}). ¿Es la tarjeta correcta?"
            )
        return resultado

    def _leer_bloques(self, id_tarjeta: object) -> dict[str, Any]:
        tarjeta = self._tarjeta_hf(id_tarjeta)
        respuesta = self._proxmark.leer_bloques(tarjeta.tipo, tarjeta.uid)
        resultado = self._guardar_volcado(tarjeta, respuesta)
        if resultado["ok"]:
            datos = respuesta.datos
            assert datos is not None
            actividad.registrar(
                self._bd,
                TipoActividad.LECTURA,
                f"Leídos {datos.bloques_leidos}/{datos.total_bloques} bloques de «{tarjeta.nombre}»",
            )
        return resultado

    def _obtener_volcado(self, id_tarjeta: object) -> dict[str, Any]:
        guardado = volcados.ultimo_volcado(self._bd, _entero(id_tarjeta, "id"))
        return {"ok": True, "volcado": conversion.volcado(guardado)}

    def _clonar_tarjeta(self, id_tarjeta: object) -> dict[str, Any]:
        tarjeta = self._tarjeta_hf(id_tarjeta)
        guardado = volcados.ultimo_volcado(self._bd, tarjeta.id)
        if guardado is None:
            return {"ok": False, "error": "No hay ningún volcado guardado. Pulsa «Leer bloques» primero."}
        volcado = guardado.volcado
        if volcado.tecnologia is not Tecnologia.MIFARE_CLASSIC:
            return {"ok": False, "error": "El clonado de Ultralight / NTAG aún no está disponible."}
        if volcado.faltan_claves:
            return {"ok": False, "error": "El volcado está incompleto (faltan claves). Pulsa «Recuperar claves» antes de clonar."}

        try:
            contenido = _bytes_volcado(volcado)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        # Seguridad: el nombre sale del UID validado como hexadecimal (recetas), y el
        # fichero se escribe solo dentro de la carpeta dumps.
        dumps = paths.carpeta_dumps().resolve()
        ruta = (dumps / recetas.nombre_archivo_volcado(tarjeta.uid)).resolve()
        if ruta.parent != dumps:
            return {"ok": False, "error": "Ruta de volcado no válida."}
        ruta.write_bytes(contenido)

        # El comando lo genera recetas.py a partir del tipo y el UID, nunca uno guardado.
        comando = recetas.derivados(tarjeta.tipo, tarjeta.uid).comando_clonado
        res = self._proxmark.ejecutar(comando, timeout=TIMEOUT_CLONADO)
        if not res.ok:
            return {"ok": False, "error": res.error or "No se pudo clonar.", "salida": res.salida}
        actividad.registrar(
            self._bd, TipoActividad.CLONADO, f"Clonada «{tarjeta.nombre}» ({tarjeta.tipo}, {tarjeta.uid})"
        )
        return {"ok": True, "salida": res.salida}

    # ---------------------------------------------------------------- escritura de bloques
    def _tecnologia(self, tipo: str) -> Tecnologia:
        if tipo in (TipoTarjeta.MIFARE_CLASSIC_1K, TipoTarjeta.MIFARE_CLASSIC_4K):
            return Tecnologia.MIFARE_CLASSIC
        if tipo == TipoTarjeta.ULTRALIGHT_NTAG:
            return Tecnologia.MIFARE_ULTRALIGHT
        raise ErrorEntrada("La escritura de bloques solo está disponible para MIFARE Classic y Ultralight / NTAG.")

    def _hex_bloque(self, tecnologia: Tecnologia, datos: object, es_texto: object) -> str:
        """Hex final del bloque a partir de texto (texto->hex) o de hex (validado)."""
        texto = _texto(datos, "datos")
        if bool(es_texto):
            return recetas.texto_a_hex(texto, recetas.bytes_por_bloque(tecnologia))
        return recetas.normalizar_datos_bloque(tecnologia, texto)

    def _preparar_datos_bloque(self, tecnologia: object, datos: object, es_texto: object) -> dict[str, Any]:
        try:
            tec = Tecnologia(_texto(tecnologia, "tecnologia"))
        except ValueError:
            return {"ok": False, "error": "Tecnología no válida."}
        try:
            hexa = self._hex_bloque(tec, datos, es_texto)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "datos_hex": hexa, "ascii": decodificadores.ascii_de_hex(hexa)}

    def _escribir_bloque(
        self,
        id_tarjeta: object,
        indice: object,
        datos: object,
        es_texto: object,
        clave: object,
        usar_clave_b: object,
        modo_experto: object,
        confirmado: object,
    ) -> dict[str, Any]:
        tarjeta = self._tarjeta_hf(id_tarjeta)
        tecnologia = self._tecnologia(tarjeta.tipo)
        bloque = _entero(indice, "bloque")
        clave_texto = _texto(clave, "clave")
        try:
            datos_hex = self._hex_bloque(tecnologia, datos, es_texto)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        trailer = recetas.es_trailer(bloque, tarjeta.tipo)
        if trailer and not bool(modo_experto):
            return {
                "ok": False,
                "es_trailer": True,
                "error": "Escribir el trailer puede bloquear el sector PARA SIEMPRE si los bits de acceso "
                "son incorrectos. Actívalo en el modo experto solo si sabes lo que haces.",
            }
        # Refuerzo: aunque sea experto y esté confirmado, un trailer con bits de
        # acceso incoherentes se rechaza (grabarlo bloquearía el sector para siempre).
        accesos = None
        if trailer:
            if not decodificadores.accesos_coherentes(datos_hex):
                return {
                    "ok": False,
                    "es_trailer": True,
                    "error": "Los bits de acceso del trailer son incoherentes; grabarlos bloquearía el "
                    "sector para siempre. Revisa los bytes 6 a 8.",
                }
            accesos = decodificadores.accesos_de_trailer(datos_hex)

        # Confirmación obligatoria (misma política que la 4b, comprobada aquí).
        if not bool(confirmado):
            return {
                "ok": False,
                "requiere_confirmacion": True,
                "bloque": bloque,
                "datos_hex": datos_hex,
                "ascii": decodificadores.ascii_de_hex(datos_hex),
                "es_trailer": trailer,
                "es_bloque0": bloque == 0,
                "accesos": accesos,
                "aviso": "Escribe solo en tarjetas propias o con autorización.",
            }

        try:
            res = self._proxmark.escribir_bloque(
                tecnologia.value, bloque, datos_hex, clave_texto, bool(usar_clave_b)
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        if not res.ok:
            if bloque == 0:
                return {
                    "ok": False,
                    "error": "No se pudo escribir el bloque 0. El bloque 0 (UID del fabricante) es de solo "
                    "lectura salvo en tarjetas mágicas (Gen1a / Gen2).",
                    "salida": res.salida,
                }
            return {"ok": False, "error": res.error or "No se pudo escribir el bloque.", "salida": res.salida}

        actividad.registrar(
            self._bd, TipoActividad.ESCRITURA, f"Escrito bloque {bloque} de «{tarjeta.nombre}»"
        )
        return {"ok": True, "bloque": bloque, "datos_hex": datos_hex, "salida": res.salida}

    def _leer_bloque(self, id_tarjeta: object, indice: object, clave: object, usar_clave_b: object) -> dict[str, Any]:
        tarjeta = self._tarjeta_hf(id_tarjeta)
        tecnologia = self._tecnologia(tarjeta.tipo)
        bloque = _entero(indice, "bloque")
        try:
            respuesta = self._proxmark.leer_bloque(tecnologia.value, bloque, _texto(clave, "clave"), bool(usar_clave_b))
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if not respuesta.ok or respuesta.datos is None:
            return {"ok": False, "error": respuesta.error or "No se pudo leer el bloque.", "salida": respuesta.salida}
        return {
            "ok": True,
            "bloque": bloque,
            "datos": respuesta.datos,
            "ascii": decodificadores.ascii_de_hex(respuesta.datos),
        }

    # ---------------------------------------------------------------- antenas
    def _listar_mediciones(self, limite: object) -> dict[str, Any]:
        n = max(1, min(_entero(limite, "limite"), MAX_MEDICIONES))
        return {
            "ok": True,
            "mediciones": [conversion.medicion(m) for m in antenas.historial(self._bd, n)],
        }

    # ---------------------------------------------------------------- emulación
    def _emular_tarjeta(self, id_tarjeta: object) -> dict[str, Any]:
        tarjeta = tarjetas.obtener(self._bd, _entero(id_tarjeta, "id"))
        if tarjeta is None:
            return {"ok": False, "error": "La tarjeta no existe (puede que se haya borrado)."}
        try:
            comando = recetas.derivados(tarjeta.tipo, tarjeta.uid).comando_emulacion
        except ValueError:
            return {"ok": False, "error": "El tipo o el UID de la tarjeta no permiten generar la emulación."}

        respuesta = self._proxmark.iniciar_emulacion(comando)
        if not respuesta.ok:
            return {"ok": False, "error": respuesta.error}
        actividad.registrar(
            self._bd, TipoActividad.EMULACION, f"Emulando «{tarjeta.nombre}» ({tarjeta.tipo})"
        )
        return {"ok": True, "estado": conversion.emulacion(respuesta.datos), "salida": respuesta.salida}

    def _detener_emulacion(self) -> dict[str, Any]:
        respuesta = self._proxmark.detener_emulacion()
        return {"ok": True, "estado": conversion.emulacion(respuesta.datos), "salida": respuesta.salida}

    def _estado_emulacion(self) -> dict[str, Any]:
        return {"ok": True, "estado": conversion.emulacion(self._proxmark.estado_emulacion())}

    # ---------------------------------------------------------------- terminal
    def _ejecutar_terminal(self, comando: object, confirmado: object) -> dict[str, Any]:
        comando = _texto(comando, "comando").strip()
        clase = _clasificar_terminal(comando)
        if clase == "vacio":
            return {"ok": False, "error": "Escribe un comando."}
        if clase == "emulacion":
            return {
                "ok": False,
                "es_emulacion": True,
                "error": "Para emular (sim) usa la sección «Clonado y emulación».",
            }
        # Por defecto se pide confirmación: solo la lista blanca de lectura corre directa.
        if clase == "confirmar" and not bool(confirmado):
            return {
                "ok": False,
                "requiere_confirmacion": True,
                "comando": comando,
                "error": "Este comando no está en la lista de lectura/diagnóstico. Confírmalo para ejecutarlo.",
            }
        res = self._proxmark.ejecutar(comando, timeout=TIMEOUT_TERMINAL)
        return {"ok": res.ok, "salida": res.salida, "error": res.error}

    def _estado_consola(self) -> dict[str, Any]:
        # El botón solo se muestra si hay cliente localizado Y puerto detectado.
        cliente = conversion.cliente_iceman(self._proxmark.buscar_cliente())
        if cliente is None:
            return {"ok": True, "disponible": False, "mensaje": "No se ha localizado el cliente de Iceman."}
        puerto = self._presencia()
        if not puerto:
            return {"ok": True, "disponible": False, "mensaje": "No se detecta ninguna Proxmark3 conectada por USB."}
        return {"ok": True, "disponible": True, "cliente": cliente, "puerto": puerto}

    def _abrir_consola(self) -> dict[str, Any]:
        respuesta = self._proxmark.abrir_consola()
        if not respuesta.ok or respuesta.datos is None:
            return {"ok": False, "error": respuesta.error}
        return {"ok": True, "puerto": respuesta.datos.puerto, "comando": respuesta.datos.comando}

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
