"""Exportar e importar tarjetas en JSON.

El archivo solo lleva datos de identificación; nunca comandos. Al importar:
- solo se leen los campos conocidos (el resto se ignora y se informa);
- cada tarjeta pasa por la misma validación que insertar_tarjeta();
- las válidas se guardan en una única transacción.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from pm3_dashboard.storage.bd import BaseDatos, fecha_texto
from pm3_dashboard.storage.tarjetas import (
    DatosNoValidos,
    NuevaTarjeta,
    es_duplicada,
    insertar_en,
    todas,
    validar,
)

FORMATO = "pm3-dashboard/tarjetas"
VERSION_FORMATO = 1
MAX_BYTES = 10 * 1024 * 1024
MAX_TARJETAS = 5000

CAMPOS = ("nombre", "notas", "fecha", "banda", "tipo", "uid", "atqa", "sak", "salida")
OBLIGATORIOS = ("nombre", "banda", "tipo", "uid")
_MAX_CAMPOS_IGNORADOS = 20


class ErrorImportacion(ValueError):
    """El archivo entero no se puede importar (no es JSON, formato desconocido, demasiado grande...)."""


@dataclass(frozen=True)
class Rechazo:
    posicion: int  # 1 = primera tarjeta del archivo
    nombre: str
    motivo: str


@dataclass(frozen=True)
class ResultadoImportacion:
    importadas: int
    rechazadas: list[Rechazo] = field(default_factory=list)
    campos_ignorados: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------
def exportar_json(bd: BaseDatos, momento: datetime | None = None) -> tuple[str, int]:
    """Devuelve (texto JSON, número de tarjetas)."""
    lista = [
        {campo: getattr(tarjeta, campo) for campo in CAMPOS}
        for tarjeta in todas(bd)
    ]
    documento = {
        "formato": FORMATO,
        "version": VERSION_FORMATO,
        "exportado": fecha_texto(momento),
        "tarjetas": lista,
    }
    return json.dumps(documento, ensure_ascii=False, indent=2), len(lista)


# ---------------------------------------------------------------------------
# Importar
# ---------------------------------------------------------------------------
def _recortar(texto: str, maximo: int = 60) -> str:
    return texto if len(texto) <= maximo else texto[: maximo - 1] + "…"


def _lista_de_tarjetas(texto: str) -> list[object]:
    """Comprueba el archivo entero y devuelve la lista de tarjetas sin validar."""
    if len(texto.encode("utf-8")) > MAX_BYTES:
        raise ErrorImportacion(f"El archivo supera el máximo de {MAX_BYTES // (1024 * 1024)} MB.")
    try:
        datos = json.loads(texto)
    except ValueError as exc:
        raise ErrorImportacion(f"El archivo no es un JSON válido ({exc}).") from exc
    if not isinstance(datos, dict) or datos.get("formato") != FORMATO:
        raise ErrorImportacion("El archivo no es una exportación de tarjetas de PM3 Dashboard.")
    if datos.get("version") != VERSION_FORMATO:
        raise ErrorImportacion(
            f"Versión de archivo no soportada ({_recortar(str(datos.get('version')), 20)}); "
            f"se esperaba la {VERSION_FORMATO}."
        )
    lista = datos.get("tarjetas")
    if not isinstance(lista, list):
        raise ErrorImportacion("El archivo no contiene una lista de tarjetas.")
    if len(lista) > MAX_TARJETAS:
        raise ErrorImportacion(f"El archivo tiene {len(lista)} tarjetas; el máximo es {MAX_TARJETAS}.")
    return lista


def _leer_tarjeta(elemento: object) -> tuple[NuevaTarjeta | None, str, str]:
    """(tarjeta, nombre para el informe, motivo del rechazo)."""
    if not isinstance(elemento, dict):
        return None, "", "no es un objeto JSON"
    nombre = _recortar(elemento["nombre"]) if isinstance(elemento.get("nombre"), str) else ""
    no_texto = [campo for campo in CAMPOS if campo in elemento and not isinstance(elemento[campo], str)]
    if no_texto:
        return None, nombre, f"campos que no son texto: {', '.join(no_texto)}"
    faltan = [campo for campo in OBLIGATORIOS if campo not in elemento]
    if faltan:
        return None, nombre, f"faltan campos obligatorios: {', '.join(faltan)}"
    tarjeta = NuevaTarjeta(**{campo: elemento[campo] for campo in CAMPOS if campo in elemento})
    try:
        validar(tarjeta)
    except DatosNoValidos as exc:
        return None, nombre, "; ".join(exc.errores)
    return tarjeta, nombre, ""


def importar_json(bd: BaseDatos, texto: str) -> ResultadoImportacion:
    """Importa las tarjetas válidas y devuelve el informe. Lanza ErrorImportacion si el archivo no sirve."""
    lista = _lista_de_tarjetas(texto)

    rechazadas: list[Rechazo] = []
    ignorados: set[str] = set()
    candidatas: list[tuple[int, NuevaTarjeta]] = []
    for posicion, elemento in enumerate(lista, start=1):
        if isinstance(elemento, dict):
            ignorados |= {_recortar(str(clave), 40) for clave in elemento if clave not in CAMPOS}
        tarjeta, nombre, motivo = _leer_tarjeta(elemento)
        if tarjeta is None:
            rechazadas.append(Rechazo(posicion, nombre, motivo))
        else:
            candidatas.append((posicion, tarjeta))

    importadas = 0
    with bd.conexion() as con:  # una sola transacción: o todas las válidas o ninguna
        for posicion, tarjeta in candidatas:
            if es_duplicada(con, tarjeta):
                rechazadas.append(
                    Rechazo(posicion, _recortar(tarjeta.nombre), "ya existe una tarjeta con el mismo nombre, tipo y UID")
                )
                continue
            insertar_en(con, tarjeta)
            importadas += 1

    return ResultadoImportacion(
        importadas=importadas,
        rechazadas=sorted(rechazadas, key=lambda r: r.posicion),
        campos_ignorados=sorted(ignorados)[:_MAX_CAMPOS_IGNORADOS],
    )
