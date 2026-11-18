"""Conversión de los datos internos a diccionarios para la interfaz (JSON)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from pm3_dashboard.pm3.localizador import OrigenCliente, ResultadoBusqueda
from pm3_dashboard.pm3.modelos import (
    InfoVersion,
    MedicionAntena,
    Respuesta,
    TarjetaLeida,
    TipoTarjeta,
)
from pm3_dashboard.pm3.parsers import MINIMO_HF_V, MINIMO_LF_V
from pm3_dashboard.pm3.recetas import derivados
from pm3_dashboard.storage.antenas import MedicionGuardada
from pm3_dashboard.storage.intercambio import ResultadoImportacion
from pm3_dashboard.storage.tarjetas import TarjetaGuardada

# ---------------------------------------------------------------------------
# Estado del dispositivo
# ---------------------------------------------------------------------------


def version_corta(linea: str) -> str:
    """'RRG/Iceman/master/v4.19552 2025-02-10 ...' -> 'v4.19552'."""
    palabras = linea.split()
    return palabras[0].rsplit("/", 1)[-1] if palabras else ""


def aviso_version(info: InfoVersion | None) -> str:
    if info is None or info.versiones_coinciden is not False:
        return ""
    return (
        f"La versión del cliente ({version_corta(info.cliente)}) no coincide con la del "
        f"firmware ({version_corta(info.firmware)}). Actualiza el firmware de la Proxmark3 "
        "para evitar fallos."
    )


def estado(respuesta: Respuesta[InfoVersion]) -> dict[str, Any]:
    info = respuesta.datos
    return {
        "conectado": respuesta.ok,
        "ocupado": False,
        "puerto": respuesta.puerto,
        "firmware": info.firmware if info else "",
        "cliente": info.cliente if info else "",
        "dispositivo": info.dispositivo if info else "",
        "version_firmware": version_corta(info.firmware) if info else "",
        "versiones_coinciden": info.versiones_coinciden if info else None,
        "aviso_version": aviso_version(info) if respuesta.ok else "",
        "mensaje": "" if respuesta.ok else respuesta.error,
    }


def estado_desconectado(mensaje: str) -> dict[str, Any]:
    return estado(Respuesta(ok=False, error=mensaje))


ETIQUETAS_ORIGEN = {
    OrigenCliente.CONFIGURADO: "Configurado",
    OrigenCliente.INCLUIDO: "Incluido",
    OrigenCliente.SISTEMA: "Sistema",
}


def cliente_iceman(busqueda: ResultadoBusqueda, version_cliente: str = "") -> dict[str, Any] | None:
    """Qué cliente se usa y de dónde sale; None si no se ha encontrado ninguno."""
    ubicacion = busqueda.ubicacion
    if ubicacion is None:
        return None
    return {
        "ruta": str(ubicacion.ruta),
        "origen": ubicacion.origen.value,
        "etiqueta": ETIQUETAS_ORIGEN[ubicacion.origen],
        "detalle": ubicacion.detalle,
        "version": version_cliente,
    }


# ---------------------------------------------------------------------------
# Antenas
# ---------------------------------------------------------------------------


def _antena(medida: MedicionAntena, minimo: float) -> dict[str, Any]:
    return {"voltios": medida.voltios, "estado": medida.estado.value, "minimo": minimo}


def medicion(guardada: MedicionGuardada | None) -> dict[str, Any] | None:
    if guardada is None:
        return None
    return {
        "fecha": guardada.fecha,
        "lf": _antena(guardada.medicion.lf, MINIMO_LF_V),
        "hf": _antena(guardada.medicion.hf, MINIMO_HF_V),
    }


def voltios_texto(medida: MedicionAntena) -> str:
    voltios = "sin datos" if medida.voltios is None else f"{medida.voltios:.2f} V"
    return f"{voltios} ({medida.estado.value})"


# ---------------------------------------------------------------------------
# Tarjetas
# ---------------------------------------------------------------------------


def derivados_de(tipo: str, uid: str) -> dict[str, str] | None:
    """Datos derivados generados con pm3/recetas.py; None si el tipo o el UID no son válidos."""
    try:
        return asdict(derivados(TipoTarjeta(tipo), uid))
    except ValueError:
        return None


def tarjeta_leida(lectura: TarjetaLeida, id_lectura: int, guardadas: list[str]) -> dict[str, Any]:
    return {**asdict(lectura), "id_lectura": id_lectura, "guardadas_con_mismo_uid": guardadas}


def tarjeta_guardada(tarjeta: TarjetaGuardada) -> dict[str, Any]:
    # Los derivados se generan aquí, nunca se leen de la BD.
    return {**asdict(tarjeta), "derivados": derivados_de(tarjeta.tipo, tarjeta.uid)}


def resultado_importacion(resultado: ResultadoImportacion, archivo: str) -> dict[str, Any]:
    return {"ok": True, "archivo": archivo, **asdict(resultado)}
