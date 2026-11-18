"""Tests de la clase Api expuesta a JavaScript."""

from __future__ import annotations

import json

from pm3_dashboard.api import Api


def test_obtener_resumen_tiene_las_claves_esperadas() -> None:
    resumen = Api().obtener_resumen()

    assert {"dispositivo", "tarjetas", "antenas", "actividad"} <= resumen.keys()
    assert {"conectado", "puerto", "firmware"} <= resumen["dispositivo"].keys()
    assert {"fecha", "lf", "hf"} <= resumen["antenas"].keys()


def test_obtener_resumen_hf_mas_lf_es_el_total() -> None:
    tarjetas = Api().obtener_resumen()["tarjetas"]

    assert tarjetas["hf"] + tarjetas["lf"] == tarjetas["total"]


def test_obtener_resumen_actividad_tiene_formato_correcto() -> None:
    actividad = Api().obtener_resumen()["actividad"]

    assert actividad, "debe haber al menos un evento de ejemplo"
    for evento in actividad:
        assert {"fecha", "tipo", "descripcion"} <= evento.keys()


def test_obtener_resumen_es_serializable_a_json() -> None:
    # pywebview envía el resultado a JavaScript como JSON.
    json.dumps(Api().obtener_resumen())
