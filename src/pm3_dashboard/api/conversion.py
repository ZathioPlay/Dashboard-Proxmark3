"""Conversión de los datos internos a diccionarios para la interfaz (JSON)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from pm3_dashboard.pm3 import decodificadores
from pm3_dashboard.pm3.localizador import OrigenCliente, ResultadoBusqueda
from pm3_dashboard.pm3.modelos import (
    EstadoEmulacion,
    InfoVersion,
    MedicionAntena,
    Respuesta,
    TarjetaLeida,
    Tecnologia,
    TipoTarjeta,
    Volcado,
)
from pm3_dashboard.pm3.parsers import MINIMO_HF_V, MINIMO_LF_V
from pm3_dashboard.pm3.recetas import derivados
from pm3_dashboard.storage.antenas import MedicionGuardada
from pm3_dashboard.storage.intercambio import ResultadoImportacion
from pm3_dashboard.storage.tarjetas import TarjetaGuardada
from pm3_dashboard.storage.volcados import VolcadoGuardado

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


def emulacion(estado: EstadoEmulacion) -> dict[str, Any]:
    return {"activa": estado.activa, "comando": estado.comando, "salida": estado.salida}


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


def _bloque_dict(bloque: Any, es_trailer: bool) -> dict[str, Any]:
    return {
        "indice": bloque.indice,
        "datos": bloque.datos,
        "leido": bloque.leido,
        "ascii": decodificadores.ascii_de_hex(bloque.datos) if bloque.leido else "",
        "es_trailer": es_trailer,
    }


def _sector_dict(sector: Any, tipo: TipoTarjeta, tecnologia: Tecnologia) -> dict[str, Any]:
    datos = {
        "indice": sector.indice,
        "completo": sector.completo,
        "clave_a": None,
        "clave_b": None,
        "accesos": None,
        "bloques": [],
    }
    es_classic = tecnologia is Tecnologia.MIFARE_CLASSIC
    indice_trailer = sector.bloques[-1].indice if sector.bloques else -1
    for bloque in sector.bloques:
        trailer = es_classic and bloque.indice == indice_trailer
        datos["bloques"].append(_bloque_dict(bloque, trailer))

    if es_classic and sector.bloques and sector.bloques[-1].leido:
        trailer_hex = sector.bloques[-1].datos
        datos["clave_a"], datos["clave_b"] = decodificadores.claves_de_trailer(trailer_hex)
        # Los sectores grandes de 4K (16 bloques) no se interpretan aquí.
        datos["accesos"] = None if len(sector.bloques) != 4 else decodificadores.accesos_de_trailer(trailer_hex)
    return datos


def _volcado_a_dict(v: Volcado, id_volcado: int | None, fecha: str) -> dict[str, Any]:
    paginas = [b.datos for sector in v.sectores for b in sector.bloques]
    ndef = (
        [asdict(r) for r in decodificadores.decodificar_ndef(paginas)]
        if v.tecnologia is Tecnologia.MIFARE_ULTRALIGHT
        else []
    )
    return {
        "id": id_volcado,
        "fecha": fecha,
        "tecnologia": v.tecnologia.value,
        "tipo": v.tipo.value,
        "uid": v.uid,
        "total_bloques": v.total_bloques,
        "bloques_leidos": v.bloques_leidos,
        "faltan_claves": v.faltan_claves,
        "completo": not v.faltan_claves,
        "sectores": [_sector_dict(s, v.tipo, v.tecnologia) for s in v.sectores],
        "ndef": ndef,
    }


def volcado(guardado: VolcadoGuardado | None) -> dict[str, Any] | None:
    """Volcado guardado en la base de datos."""
    if guardado is None:
        return None
    return _volcado_a_dict(guardado.volcado, guardado.id, guardado.fecha)


def volcado_bruto(v: Volcado, fecha: str) -> dict[str, Any]:
    """Volcado aún no guardado (lectura sobre una tarjeta recién escaneada)."""
    return _volcado_a_dict(v, None, fecha)
