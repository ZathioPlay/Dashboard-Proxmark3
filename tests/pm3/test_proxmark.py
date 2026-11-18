"""Tests de la fachada Proxmark3 (flujo completo con el cliente falso)."""

from __future__ import annotations

import json
from dataclasses import asdict

from pm3_dashboard.pm3.modelos import Banda, EstadoAntena
from pm3_dashboard.pm3.proxmark import MSG_SIN_TARJETA, Proxmark3
from tests.pm3.falsos import LanzadorFalso, cargar_muestra


def test_estado_conectado(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hw version", stdout=cargar_muestra("hw_version"))

    respuesta = proxmark.estado()

    assert respuesta.ok
    assert respuesta.puerto == "COM5"
    assert respuesta.datos is not None
    assert respuesta.datos.dispositivo == "RDV4"


def test_estado_sin_conexion(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hw version", stdout=cargar_muestra("sin_conexion"))

    respuesta = proxmark.estado()

    assert not respuesta.ok
    assert respuesta.datos is None
    assert "No se pudo comunicar" in respuesta.error


def test_medir_antenas(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hw tune", stdout=cargar_muestra("hw_tune_ok"))

    respuesta = proxmark.medir_antenas()

    assert respuesta.ok
    assert respuesta.datos is not None
    assert respuesta.datos.lf.voltios == 44.28
    assert respuesta.datos.hf.estado is EstadoAntena.OK


def test_medir_antenas_con_error(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hw tune", codigo=1)

    respuesta = proxmark.medir_antenas()

    assert not respuesta.ok
    assert respuesta.datos is None


def test_escanear_auto_encuentra_hf(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hf search", stdout=cargar_muestra("hf_search_1k"))

    respuesta = proxmark.escanear("auto")

    assert respuesta.ok
    assert respuesta.datos is not None
    assert respuesta.datos.banda is Banda.HF
    assert respuesta.datos.uid == "5A 3E 7C 1B"
    assert respuesta.datos.fecha == "2026-11-18"
    assert lanzador.comandos == ["hf search"]  # no hace falta probar LF


def test_escanear_auto_pasa_a_lf_si_no_hay_hf(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hf search", stdout=cargar_muestra("hf_search_vacio"))
    lanzador.responder("lf search", stdout=cargar_muestra("lf_search_em410x"))

    respuesta = proxmark.escanear("auto")

    assert respuesta.ok
    assert respuesta.datos is not None
    assert respuesta.datos.banda is Banda.LF
    assert respuesta.datos.uid == "0F 03 68 56 8B"
    assert lanzador.comandos == ["hf search", "lf search"]


def test_escanear_auto_pasa_a_lf_aunque_falle_hf(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hf search", codigo=1)
    lanzador.responder("lf search", stdout=cargar_muestra("lf_search_em410x"))

    assert proxmark.escanear("auto").ok


def test_escanear_sin_tarjeta(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hf search", stdout=cargar_muestra("hf_search_vacio"))
    lanzador.responder("lf search", stdout=cargar_muestra("lf_search_vacio"))

    respuesta = proxmark.escanear("auto")

    assert not respuesta.ok
    assert respuesta.error == MSG_SIN_TARJETA


def test_escanear_solo_hf_con_error(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hf search", codigo=1, stderr="fallo HF")

    respuesta = proxmark.escanear("hf")

    assert not respuesta.ok
    assert respuesta.error == "fallo HF"
    assert lanzador.comandos == ["hf search"]


def test_escanear_solo_lf(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("lf search", stdout=cargar_muestra("lf_search_em410x"))

    assert proxmark.escanear("lf").ok
    assert lanzador.comandos == ["lf search"]


def test_escanear_banda_no_valida(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    respuesta = proxmark.escanear("uhf")

    assert not respuesta.ok
    assert lanzador.llamadas == []


def test_las_respuestas_se_pueden_pasar_a_json(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    # En la fase 3 la Api devolverá asdict(respuesta) a JavaScript.
    lanzador.responder("hf search", stdout=cargar_muestra("hf_search_ntag"))

    datos = json.loads(json.dumps(asdict(proxmark.escanear())))

    assert datos["datos"]["banda"] == "hf"
    assert datos["datos"]["tipo"] == "MIFARE Ultralight / NTAG"


# ---------------------------------------------------------------- volcado y recuperación de claves

from pm3_dashboard.pm3.modelos import Tecnologia, TipoTarjeta  # noqa: E402


def test_leer_bloques_classic(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hf mf dump", stdout=cargar_muestra("hf_mf_dump_1k_completo"))

    respuesta = proxmark.leer_bloques(TipoTarjeta.MIFARE_CLASSIC_1K, "5A 3E 7C 1B")

    assert respuesta.ok
    assert respuesta.datos is not None
    assert respuesta.datos.tecnologia is Tecnologia.MIFARE_CLASSIC
    assert respuesta.datos.bloques_leidos == 64
    assert lanzador.comandos == ["hf mf dump"]


def test_leer_bloques_ultralight_usa_mfu_dump(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hf mfu dump", stdout=cargar_muestra("hf_mfu_dump"))

    respuesta = proxmark.leer_bloques(TipoTarjeta.ULTRALIGHT_NTAG, "04 68 95 71")

    assert respuesta.ok
    assert respuesta.datos is not None and respuesta.datos.tecnologia is Tecnologia.MIFARE_ULTRALIGHT
    assert lanzador.comandos == ["hf mfu dump"]


def test_leer_bloques_con_error_de_hardware(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hf mf dump", codigo=1, stderr="sin tarjeta")

    respuesta = proxmark.leer_bloques(TipoTarjeta.MIFARE_CLASSIC_1K, "5A3E7C1B")

    assert not respuesta.ok
    assert respuesta.datos is None


def test_recuperar_claves_usa_autopwn(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hf mf autopwn", stdout=cargar_muestra("hf_mf_autopwn"))

    respuesta = proxmark.recuperar_claves("5A3E7C1B", TipoTarjeta.MIFARE_CLASSIC_1K)

    assert respuesta.ok
    assert respuesta.datos is not None and respuesta.datos.bloques_leidos == 64
    assert lanzador.comandos == ["hf mf autopwn"]


def test_recuperar_claves_solo_classic(proxmark: Proxmark3, lanzador: LanzadorFalso) -> None:
    respuesta = proxmark.recuperar_claves("04689571", TipoTarjeta.ULTRALIGHT_NTAG)

    assert not respuesta.ok
    assert lanzador.llamadas == []
