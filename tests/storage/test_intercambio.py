"""Tests de exportar e importar tarjetas en JSON, incluidos archivos malos o manipulados."""

from __future__ import annotations

import json
from typing import Any

import pytest

from pm3_dashboard.storage import BaseDatos
from pm3_dashboard.storage.intercambio import (
    FORMATO,
    MAX_BYTES,
    MAX_TARJETAS,
    ErrorImportacion,
    exportar_json,
    importar_json,
)
from pm3_dashboard.storage.tarjetas import NuevaTarjeta, insertar_tarjeta, listar, todas

BUENA_HF: dict[str, Any] = {
    "nombre": "Tarjeta oficina", "notas": "", "fecha": "2026-11-17 10:00:00", "banda": "hf",
    "tipo": "MIFARE Classic 1K", "uid": "5A 3E 7C 1B", "atqa": "00 04", "sak": "08", "salida": "[+] UID...",
}
BUENA_LF: dict[str, Any] = {"nombre": "Llavero", "banda": "lf", "tipo": "EM410x", "uid": "0F0368568B"}


def _archivo(tarjetas: list[Any], **extra: Any) -> str:
    return json.dumps({"formato": FORMATO, "version": 1, "tarjetas": tarjetas, **extra})


# ---------------------------------------------------------------- exportar


def test_exportar_e_importar_conserva_los_datos(bd: BaseDatos, tmp_path) -> None:
    insertar_tarjeta(bd, NuevaTarjeta(**BUENA_HF))
    insertar_tarjeta(bd, NuevaTarjeta(**BUENA_LF, notas="con «comillas» y ñ"))
    texto, cantidad = exportar_json(bd)

    otra = BaseDatos(tmp_path / "otra.db")
    resultado = importar_json(otra, texto)

    assert cantidad == 2
    assert resultado.importadas == 2 and resultado.rechazadas == []
    sin_id = lambda bd_: [{**t.__dict__, "id": None} for t in todas(bd_)]  # noqa: E731
    assert sin_id(otra) == sin_id(bd)


def test_el_archivo_exportado_no_lleva_comandos(bd: BaseDatos) -> None:
    insertar_tarjeta(bd, NuevaTarjeta(**BUENA_LF))
    texto, _ = exportar_json(bd)
    documento = json.loads(texto)

    assert documento["formato"] == FORMATO and documento["version"] == 1
    assert set(documento["tarjetas"][0]) == {"nombre", "notas", "fecha", "banda", "tipo", "uid", "atqa", "sak", "salida"}
    assert "sim" not in texto and "clone" not in texto


def test_exportar_sin_tarjetas(bd: BaseDatos) -> None:
    texto, cantidad = exportar_json(bd)

    assert cantidad == 0
    assert json.loads(texto)["tarjetas"] == []


# ---------------------------------------------------------------- archivo entero no válido


@pytest.mark.parametrize(
    ("texto", "fragmento"),
    [
        ("{ esto no es json", "no es un JSON válido"),
        ("[]", "no es una exportación"),
        (json.dumps({"tarjetas": []}), "no es una exportación"),
        (json.dumps({"formato": "otro", "version": 1, "tarjetas": []}), "no es una exportación"),
        (json.dumps({"formato": FORMATO, "version": 99, "tarjetas": []}), "Versión de archivo no soportada"),
        (json.dumps({"formato": FORMATO, "version": "1", "tarjetas": []}), "Versión de archivo no soportada"),
        (json.dumps({"formato": FORMATO, "version": 1, "tarjetas": {"a": 1}}), "no contiene una lista"),
    ],
)
def test_archivos_que_no_se_pueden_importar(bd: BaseDatos, texto: str, fragmento: str) -> None:
    with pytest.raises(ErrorImportacion, match=fragmento):
        importar_json(bd, texto)
    assert listar(bd) == []


def test_archivo_demasiado_grande(bd: BaseDatos) -> None:
    with pytest.raises(ErrorImportacion, match="supera el máximo"):
        importar_json(bd, " " * (MAX_BYTES + 1))


def test_demasiadas_tarjetas(bd: BaseDatos) -> None:
    with pytest.raises(ErrorImportacion, match="el máximo es"):
        importar_json(bd, _archivo([BUENA_LF] * (MAX_TARJETAS + 1)))


# ---------------------------------------------------------------- tarjetas no válidas


@pytest.mark.parametrize(
    ("elemento", "fragmento"),
    [
        ("no soy un objeto", "no es un objeto JSON"),
        ([1, 2, 3], "no es un objeto JSON"),
        ({**BUENA_LF, "uid": 123456}, "campos que no son texto: uid"),
        ({**BUENA_LF, "nombre": None}, "campos que no son texto: nombre"),
        ({"nombre": "x", "banda": "lf"}, "faltan campos obligatorios: tipo, uid"),
        ({**BUENA_LF, "uid": "ZZZZ"}, "hexadecimal"),
        ({**BUENA_LF, "banda": "uhf"}, "banda desconocida"),
        ({**BUENA_LF, "tipo": "Desconocida"}, "no válido para LF"),
        ({**BUENA_LF, "tipo": "EM410x (EM4100)"}, "no válido para LF"),  # texto antiguo
        ({**BUENA_LF, "nombre": "x" * 500}, "nombre supera"),
        ({**BUENA_LF, "fecha": "<script>"}, "fecha debe tener el formato"),
    ],
)
def test_tarjetas_no_validas_se_rechazan_con_motivo(bd: BaseDatos, elemento: Any, fragmento: str) -> None:
    resultado = importar_json(bd, _archivo([elemento]))

    assert resultado.importadas == 0
    assert len(resultado.rechazadas) == 1
    assert resultado.rechazadas[0].posicion == 1
    assert fragmento in resultado.rechazadas[0].motivo
    assert listar(bd) == []


# ---------------------------------------------------------------- comandos inyectados


def test_comandos_en_el_archivo_se_ignoran_y_nunca_se_guardan(bd: BaseDatos) -> None:
    con_comandos = {
        **BUENA_LF,
        "comando_clonado": "lf t55xx wipe",
        "comando_emulacion": "hw tune",
        "clone_cmd": "lf t55xx wipe",
        "cloneCmd": "lf t55xx wipe",
        "sim_cmd": "hf mf wrbl --blk 0",
        "tarjeta_destino": "<img src=x onerror=alert(1)>",
        "derivados": {"comando_clonado": "lf t55xx wipe"},
    }

    resultado = importar_json(bd, _archivo([con_comandos]))

    assert resultado.importadas == 1
    assert {"comando_clonado", "comando_emulacion", "clone_cmd", "cloneCmd", "sim_cmd", "derivados"} <= set(
        resultado.campos_ignorados
    )
    with bd.conexion() as con:
        volcado = "\n".join(str(tuple(fila)) for fila in con.execute("SELECT * FROM tarjetas"))
    assert "wipe" not in volcado and "wrbl" not in volcado and "onerror" not in volcado


@pytest.mark.parametrize(
    "cambios",
    [
        {"uid": "0F0368568B; lf t55xx wipe"},
        {"uid": "0F0368568B\nhw tune"},
        {"tipo": "EM410x; lf t55xx wipe"},
        {"banda": "lf; hw tune"},
    ],
)
def test_comandos_metidos_en_los_campos_se_rechazan(bd: BaseDatos, cambios: dict[str, str]) -> None:
    resultado = importar_json(bd, _archivo([{**BUENA_LF, **cambios}]))

    assert resultado.importadas == 0
    assert len(resultado.rechazadas) == 1
    assert listar(bd) == []


def test_campos_ignorados_muy_largos_se_recortan(bd: BaseDatos) -> None:
    resultado = importar_json(bd, _archivo([{**BUENA_LF, "x" * 1000: "y"}]))

    assert resultado.importadas == 1
    assert len(resultado.campos_ignorados[0]) <= 40


# ---------------------------------------------------------------- mezcla y duplicados


def test_mezcla_de_buenas_y_malas(bd: BaseDatos) -> None:
    archivo = _archivo([
        BUENA_HF,
        {**BUENA_LF, "uid": "malo"},
        "basura",
        BUENA_LF,
        {**BUENA_HF, "nombre": ""},
    ])

    resultado = importar_json(bd, archivo)

    assert resultado.importadas == 2
    assert [r.posicion for r in resultado.rechazadas] == [2, 3, 5]
    assert resultado.rechazadas[0].nombre == "Llavero"
    assert sorted(t.nombre for t in listar(bd)) == ["Llavero", "Tarjeta oficina"]


def test_importar_dos_veces_no_duplica(bd: BaseDatos) -> None:
    archivo = _archivo([BUENA_HF, BUENA_LF])
    importar_json(bd, archivo)

    segunda = importar_json(bd, archivo)

    assert segunda.importadas == 0
    assert all("ya existe" in r.motivo for r in segunda.rechazadas)
    assert len(listar(bd)) == 2


def test_duplicadas_dentro_del_mismo_archivo(bd: BaseDatos) -> None:
    resultado = importar_json(bd, _archivo([BUENA_LF, {**BUENA_LF, "uid": "0f 03 68 56 8b"}]))

    assert resultado.importadas == 1
    assert resultado.rechazadas[0].posicion == 2


def test_misma_tarjeta_con_otro_nombre_si_se_importa(bd: BaseDatos) -> None:
    resultado = importar_json(bd, _archivo([BUENA_LF, {**BUENA_LF, "nombre": "Copia"}]))

    assert resultado.importadas == 2
