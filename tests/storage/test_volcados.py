"""Tests del almacenamiento de volcados de memoria."""

from __future__ import annotations

import pytest

from pm3_dashboard.pm3.modelos import BloqueMemoria, SectorMemoria, Tecnologia, TipoTarjeta, Volcado
from pm3_dashboard.storage import BaseDatos
from pm3_dashboard.storage.migraciones import MIGRACIONES
from pm3_dashboard.storage.tarjetas import NuevaTarjeta, insertar_tarjeta
from pm3_dashboard.storage.volcados import guardar_volcado, ultimo_volcado

TARJETA = NuevaTarjeta(nombre="Oficina", banda="hf", tipo="MIFARE Classic 1K", uid="5A3E7C1B")


def _volcado(faltan: bool = False) -> Volcado:
    bloques = [BloqueMemoria(indice=i, datos="00 " * 15 + "00", leido=True) for i in range(4)]
    if faltan:
        bloques[2] = BloqueMemoria(indice=2, datos="", leido=False)
    sector = SectorMemoria(indice=0, bloques=bloques, completo=not faltan)
    return Volcado(
        tecnologia=Tecnologia.MIFARE_CLASSIC, tipo=TipoTarjeta.MIFARE_CLASSIC_1K, uid="5A3E7C1B",
        sectores=[sector], total_bloques=4, bloques_leidos=3 if faltan else 4, faltan_claves=faltan,
    )


@pytest.fixture
def tarjeta_id(bd: BaseDatos) -> int:
    return insertar_tarjeta(bd, TARJETA)


def test_migracion_v2_crea_la_tabla(bd: BaseDatos) -> None:
    bd.migrar()
    with bd.conexion() as con:
        tablas = {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "volcados" in tablas
    assert bd.version() == len(MIGRACIONES)


def test_guardar_y_leer_el_ultimo(bd: BaseDatos, tarjeta_id: int) -> None:
    assert ultimo_volcado(bd, tarjeta_id) is None

    guardar_volcado(bd, tarjeta_id, _volcado(faltan=True), salida="salida vieja")
    guardado = guardar_volcado(bd, tarjeta_id, _volcado(faltan=False), salida="[=] dump")

    leido = ultimo_volcado(bd, tarjeta_id)
    assert leido is not None
    assert leido.id == guardado.id  # el más reciente
    assert leido.volcado == _volcado(faltan=False)
    assert leido.volcado.faltan_claves is False


def test_el_volcado_se_borra_con_la_tarjeta(bd: BaseDatos, tarjeta_id: int) -> None:
    guardar_volcado(bd, tarjeta_id, _volcado())

    with bd.conexion() as con:
        con.execute("DELETE FROM tarjetas WHERE id = ?", (tarjeta_id,))

    with bd.conexion() as con:
        assert con.execute("SELECT COUNT(*) FROM volcados").fetchone()[0] == 0
