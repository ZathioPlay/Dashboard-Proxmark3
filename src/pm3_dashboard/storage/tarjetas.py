"""Tarjetas guardadas: validación, alta, búsqueda, edición y borrado.

Solo se guardan los datos de identificación (tipo canónico, UID, ATQA/SAK) y
la salida del cliente. Los datos derivados y los comandos NO se guardan: se
generan siempre con pm3/recetas.py.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from pm3_dashboard.pm3.modelos import Banda, TipoTarjeta
from pm3_dashboard.storage.bd import BaseDatos, fecha_texto

MAX_NOMBRE = 100
MAX_NOTAS = 2000
MAX_SALIDA = 100_000
MAX_ATQA_SAK = 32
MAX_RESULTADOS = 1000

# Tamaños de UID válidos por banda (bytes): ISO14443-A tiene UID de 4, 7 o 10
# bytes; el ID de EM410x es de 5 bytes.
BYTES_UID: dict[str, frozenset[int]] = {
    Banda.HF: frozenset({4, 7, 10}),
    Banda.LF: frozenset({5}),
}

_RE_HEX = re.compile(r"[0-9A-Fa-f]+")
_RE_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?")
_COLUMNAS = "id, nombre, notas, fecha, banda, tipo, uid, atqa, sak"


class DatosNoValidos(ValueError):
    """Los datos de la tarjeta no son válidos. El mensaje lista todos los problemas."""

    def __init__(self, errores: list[str]) -> None:
        self.errores = errores
        super().__init__("Datos de la tarjeta no válidos: " + "; ".join(errores) + ".")


@dataclass(frozen=True)
class NuevaTarjeta:
    nombre: str
    banda: str
    tipo: str
    uid: str
    fecha: str = ""  # fecha de lectura; vacía = ahora
    notas: str = ""
    atqa: str = ""
    sak: str = ""
    salida: str = ""


@dataclass(frozen=True)
class TarjetaGuardada:
    id: int
    nombre: str
    notas: str
    fecha: str
    banda: str
    tipo: str  # texto tal cual está en la BD (podría no ser un TipoTarjeta si se editó a mano)
    uid: str
    atqa: str
    sak: str
    salida: str = ""  # vacía en los listados; completa con obtener()


# ---------------------------------------------------------------------------
# Validación (la usan insertar_tarjeta y la importación)
# ---------------------------------------------------------------------------
def normalizar_uid(uid: str) -> str | None:
    """'04a1B2c3' o '04 A1 B2 C3' -> '04 A1 B2 C3'. None si no es hexadecimal con nº par de dígitos."""
    compacto = "".join(uid.split())
    if not _RE_HEX.fullmatch(compacto) or len(compacto) % 2:
        return None
    compacto = compacto.upper()
    return " ".join(compacto[i : i + 2] for i in range(0, len(compacto), 2))


def _errores_texto(nombre: str, notas: str) -> list[str]:
    errores: list[str] = []
    nombre = nombre.strip()
    if not nombre:
        errores.append("el nombre no puede estar vacío")
    elif len(nombre) > MAX_NOMBRE:
        errores.append(f"el nombre supera los {MAX_NOMBRE} caracteres")
    if len(notas) > MAX_NOTAS:
        errores.append(f"las notas superan los {MAX_NOTAS} caracteres")
    return errores


def _errores_identificacion(banda: str, tipo: str, uid: str) -> list[str]:
    if banda not in BYTES_UID:
        return [f"banda desconocida {banda[:20]!r} (debe ser 'hf' o 'lf')"]

    errores: list[str] = []
    validos = {t.value for t in TipoTarjeta.de_banda(banda)}
    if tipo not in validos:
        errores.append(
            f"tipo {tipo[:40]!r} no válido para {banda.upper()} (válidos: {', '.join(sorted(validos))})"
        )

    normalizado = normalizar_uid(uid)
    tamanos = ", ".join(str(n) for n in sorted(BYTES_UID[banda]))
    if normalizado is None:
        errores.append("el UID/ID debe ser hexadecimal con un número par de dígitos")
    elif len(normalizado.split()) not in BYTES_UID[banda]:
        errores.append(f"un UID/ID de {banda.upper()} debe tener {tamanos} bytes")
    return errores


def _errores(tarjeta: NuevaTarjeta) -> list[str]:
    errores = _errores_texto(tarjeta.nombre, tarjeta.notas)
    errores += _errores_identificacion(tarjeta.banda, tarjeta.tipo, tarjeta.uid)
    if tarjeta.fecha and not _RE_FECHA.fullmatch(tarjeta.fecha):
        errores.append("la fecha debe tener el formato AAAA-MM-DD o AAAA-MM-DD HH:MM:SS")
    if len(tarjeta.salida) > MAX_SALIDA:
        errores.append(f"la salida del cliente supera los {MAX_SALIDA} caracteres")
    if len(tarjeta.atqa) > MAX_ATQA_SAK or len(tarjeta.sak) > MAX_ATQA_SAK:
        errores.append(f"ATQA y SAK no pueden superar los {MAX_ATQA_SAK} caracteres")
    return errores


def validar(tarjeta: NuevaTarjeta) -> None:
    """Lanza DatosNoValidos con todos los problemas encontrados."""
    errores = _errores(tarjeta)
    if errores:
        raise DatosNoValidos(errores)


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------
def insertar_en(con: sqlite3.Connection, tarjeta: NuevaTarjeta) -> int:
    """Valida e inserta usando una conexión ya abierta (para importar en una sola transacción)."""
    validar(tarjeta)
    cursor = con.execute(
        """INSERT INTO tarjetas (nombre, notas, fecha, banda, tipo, uid, atqa, sak, salida)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            tarjeta.nombre.strip(),
            tarjeta.notas,
            tarjeta.fecha or fecha_texto(),
            tarjeta.banda,
            tarjeta.tipo,
            normalizar_uid(tarjeta.uid),
            tarjeta.atqa.strip().upper(),
            tarjeta.sak.strip().upper(),
            tarjeta.salida,
        ),
    )
    return int(cursor.lastrowid or 0)


def insertar_tarjeta(bd: BaseDatos, tarjeta: NuevaTarjeta) -> int:
    """Valida y guarda la tarjeta. Devuelve su id. Si no es válida, no guarda nada."""
    validar(tarjeta)
    with bd.conexion() as con:
        return insertar_en(con, tarjeta)


def es_duplicada(con: sqlite3.Connection, tarjeta: NuevaTarjeta) -> bool:
    """Ya existe una con el mismo nombre, tipo y UID."""
    fila = con.execute(
        "SELECT 1 FROM tarjetas WHERE nombre = ? AND tipo = ? AND uid = ? LIMIT 1",
        (tarjeta.nombre.strip(), tarjeta.tipo, normalizar_uid(tarjeta.uid)),
    ).fetchone()
    return fila is not None


def actualizar(bd: BaseDatos, id_tarjeta: int, nombre: str, notas: str) -> bool:
    """Cambia nombre y notas. Devuelve False si la tarjeta no existe."""
    errores = _errores_texto(nombre, notas)
    if errores:
        raise DatosNoValidos(errores)
    with bd.conexion() as con:
        cursor = con.execute(
            "UPDATE tarjetas SET nombre = ?, notas = ? WHERE id = ?", (nombre.strip(), notas, id_tarjeta)
        )
        return cursor.rowcount > 0


def borrar(bd: BaseDatos, id_tarjeta: int) -> bool:
    """Devuelve False si la tarjeta no existía."""
    with bd.conexion() as con:
        return con.execute("DELETE FROM tarjetas WHERE id = ?", (id_tarjeta,)).rowcount > 0


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------
def _escapar_like(texto: str) -> str:
    """Para que '%' y '_' se busquen como texto normal."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def listar(bd: BaseDatos, texto: str = "", banda: str = "") -> list[TarjetaGuardada]:
    """Busca en nombre, notas y UID (con o sin espacios). Sin la salida completa."""
    condiciones: list[str] = []
    parametros: list[object] = []
    if banda:
        if banda not in BYTES_UID:
            raise DatosNoValidos([f"banda desconocida {banda[:20]!r} (debe ser 'hf' o 'lf')"])
        condiciones.append("banda = ?")
        parametros.append(banda)
    texto = texto.strip()
    if texto:
        patron = f"%{_escapar_like(texto)}%"
        patron_uid = f"%{_escapar_like(''.join(texto.split()))}%"
        condiciones.append(
            "(nombre LIKE ? ESCAPE '\\' OR notas LIKE ? ESCAPE '\\' "
            "OR REPLACE(uid, ' ', '') LIKE ? ESCAPE '\\')"
        )
        parametros += [patron, patron, patron_uid]

    donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    with bd.conexion() as con:
        filas = con.execute(
            f"SELECT {_COLUMNAS} FROM tarjetas {donde} ORDER BY fecha DESC, id DESC LIMIT ?",
            (*parametros, MAX_RESULTADOS),
        ).fetchall()
    return [TarjetaGuardada(**dict(fila)) for fila in filas]


def obtener(bd: BaseDatos, id_tarjeta: int) -> TarjetaGuardada | None:
    """Tarjeta completa, con la salida del cliente."""
    with bd.conexion() as con:
        fila = con.execute(f"SELECT {_COLUMNAS}, salida FROM tarjetas WHERE id = ?", (id_tarjeta,)).fetchone()
    return TarjetaGuardada(**dict(fila)) if fila else None


def todas(bd: BaseDatos) -> list[TarjetaGuardada]:
    """Todas, completas y en orden de alta (para exportar)."""
    with bd.conexion() as con:
        filas = con.execute(f"SELECT {_COLUMNAS}, salida FROM tarjetas ORDER BY id").fetchall()
    return [TarjetaGuardada(**dict(fila)) for fila in filas]


def nombres_con_uid(bd: BaseDatos, uid: str) -> list[str]:
    """Nombres de las tarjetas guardadas con ese UID (para avisar al leer)."""
    normalizado = normalizar_uid(uid)
    if normalizado is None:
        return []
    with bd.conexion() as con:
        filas = con.execute("SELECT nombre FROM tarjetas WHERE uid = ? ORDER BY id", (normalizado,)).fetchall()
    return [fila["nombre"] for fila in filas]


def contar_por_banda(bd: BaseDatos) -> dict[str, int]:
    """{'total': n, 'hf': n, 'lf': n}."""
    with bd.conexion() as con:
        filas = con.execute("SELECT banda, COUNT(*) AS n FROM tarjetas GROUP BY banda").fetchall()
    cuentas = {"hf": 0, "lf": 0}
    for fila in filas:
        cuentas[fila["banda"]] = fila["n"]
    return {"total": cuentas["hf"] + cuentas["lf"], **cuentas}
