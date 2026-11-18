"""Volcados de memoria guardados (leer bloques HF).

El volcado es un dato leído de la tarjeta: los bloques se guardan como JSON,
nunca como un comando. Se borra en cascada al borrar la tarjeta.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime

from pm3_dashboard.pm3.modelos import BloqueMemoria, SectorMemoria, Tecnologia, TipoTarjeta, Volcado
from pm3_dashboard.storage.bd import BaseDatos, fecha_texto


@dataclass(frozen=True)
class VolcadoGuardado:
    id: int
    fecha: str
    volcado: Volcado


def _volcado_a_json(volcado: Volcado) -> str:
    return json.dumps(
        {
            "tecnologia": volcado.tecnologia.value,
            "tipo": volcado.tipo.value,
            "uid": volcado.uid,
            "faltan_claves": volcado.faltan_claves,
            "sectores": [asdict(sector) for sector in volcado.sectores],
        },
        ensure_ascii=False,
    )


def _volcado_desde_json(
    datos_json: str, bloques_leidos: int, total_bloques: int
) -> Volcado:
    datos = json.loads(datos_json)
    sectores = [
        SectorMemoria(
            indice=sector["indice"],
            bloques=[BloqueMemoria(**bloque) for bloque in sector["bloques"]],
            completo=sector["completo"],
        )
        for sector in datos["sectores"]
    ]
    return Volcado(
        tecnologia=Tecnologia(datos["tecnologia"]),
        tipo=TipoTarjeta(datos["tipo"]),
        uid=datos["uid"],
        sectores=sectores,
        total_bloques=total_bloques,
        bloques_leidos=bloques_leidos,
        faltan_claves=datos["faltan_claves"],
    )


def guardar_volcado(
    bd: BaseDatos, tarjeta_id: int, volcado: Volcado, salida: str = "", momento: datetime | None = None
) -> VolcadoGuardado:
    fecha = fecha_texto(momento)
    with bd.conexion() as con:
        cursor = con.execute(
            """INSERT INTO volcados
               (tarjeta_id, fecha, tecnologia, bloques_leidos, total_bloques, completo, salida, datos_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tarjeta_id,
                fecha,
                volcado.tecnologia.value,
                volcado.bloques_leidos,
                volcado.total_bloques,
                int(not volcado.faltan_claves),
                salida,
                _volcado_a_json(volcado),
            ),
        )
        return VolcadoGuardado(id=int(cursor.lastrowid or 0), fecha=fecha, volcado=volcado)


def ultimo_volcado(bd: BaseDatos, tarjeta_id: int) -> VolcadoGuardado | None:
    with bd.conexion() as con:
        fila = con.execute(
            "SELECT * FROM volcados WHERE tarjeta_id = ? ORDER BY fecha DESC, id DESC LIMIT 1",
            (tarjeta_id,),
        ).fetchone()
    if fila is None:
        return None
    return VolcadoGuardado(
        id=fila["id"],
        fecha=fila["fecha"],
        volcado=_volcado_desde_json(fila["datos_json"], fila["bloques_leidos"], fila["total_bloques"]),
    )
