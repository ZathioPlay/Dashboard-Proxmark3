"""Tests de las tarjetas guardadas: validación, alta, búsqueda, edición y borrado."""

from __future__ import annotations

from dataclasses import replace

import pytest

from pm3_dashboard.storage import BaseDatos, DatosNoValidos
from pm3_dashboard.storage.tarjetas import (
    MAX_NOMBRE,
    MAX_NOTAS,
    MAX_SALIDA,
    NuevaTarjeta,
    actualizar,
    borrar,
    contar_por_banda,
    insertar_tarjeta,
    listar,
    nombres_con_uid,
    normalizar_uid,
    obtener,
)

HF = NuevaTarjeta(
    nombre="Tarjeta oficina", banda="hf", tipo="MIFARE Classic 1K", uid="5a3e7c1b",
    atqa="00 04", sak="08", fecha="2026-11-17 10:00:00", salida="[+] UID: 5A 3E 7C 1B",
)
NTAG = NuevaTarjeta(
    nombre="Pegatina 50%_descuento", banda="hf", tipo="MIFARE Ultralight / NTAG",
    uid="04 68 95 71 FA 5C 64", notas="del congreso", fecha="2026-11-18 09:00:00",
)
LF = NuevaTarjeta(
    nombre="Llavero portal", banda="lf", tipo="EM410x", uid="0F0368568B", fecha="2026-11-16 08:00:00"
)


@pytest.fixture
def con_tres(bd: BaseDatos) -> dict[str, int]:
    return {"hf": insertar_tarjeta(bd, HF), "ntag": insertar_tarjeta(bd, NTAG), "lf": insertar_tarjeta(bd, LF)}


# ---------------------------------------------------------------- alta y validación


def test_insertar_normaliza_y_guarda(bd: BaseDatos) -> None:
    id_tarjeta = insertar_tarjeta(bd, replace(HF, nombre="  Tarjeta oficina  ", fecha=""))

    tarjeta = obtener(bd, id_tarjeta)
    assert tarjeta is not None
    assert tarjeta.uid == "5A 3E 7C 1B"
    assert tarjeta.nombre == "Tarjeta oficina"
    assert tarjeta.fecha  # se pone la fecha actual si no se indica
    assert tarjeta.salida == "[+] UID: 5A 3E 7C 1B"


def test_contar_por_banda(bd: BaseDatos, con_tres: dict[str, int]) -> None:
    assert contar_por_banda(bd) == {"total": 3, "hf": 2, "lf": 1}


@pytest.mark.parametrize(
    ("uid", "esperado"),
    [
        ("04a1b2c3", "04 A1 B2 C3"),
        ("04 A1 B2 C3", "04 A1 B2 C3"),
        (" 0f03\t68568b ", "0F 03 68 56 8B"),
        ("", None),
        ("XYZ1", None),
        ("04A1B", None),  # número impar de dígitos
        ("0F0368568B; hw tune", None),
    ],
)
def test_normalizar_uid(uid: str, esperado: str | None) -> None:
    assert normalizar_uid(uid) == esperado


@pytest.mark.parametrize(
    ("cambios", "fragmento"),
    [
        ({"banda": "uhf"}, "banda desconocida"),
        ({"uid": "no-es-hex"}, "hexadecimal"),
        ({"uid": "04A1B"}, "hexadecimal"),
        ({"uid": "04 A1 B2"}, "debe tener 4, 7, 10 bytes"),
        ({"tipo": "Tarjeta inventada"}, "tipo 'Tarjeta inventada' no válido"),
        ({"tipo": "EM410x"}, "no válido para HF"),  # tipo de LF con banda HF
        ({"tipo": "ISO14443-A (HF)"}, "no válido para HF"),  # texto antiguo de la fase 2/3
        ({"nombre": "   "}, "nombre no puede estar vacío"),
        ({"nombre": "x" * (MAX_NOMBRE + 1)}, "nombre supera"),
        ({"notas": "x" * (MAX_NOTAS + 1)}, "notas superan"),
        ({"salida": "x" * (MAX_SALIDA + 1)}, "salida del cliente supera"),
        ({"atqa": "0" * 33}, "ATQA y SAK"),
        ({"fecha": "ayer"}, "fecha debe tener el formato"),
    ],
)
def test_datos_no_validos_no_se_guardan(bd: BaseDatos, cambios: dict, fragmento: str) -> None:
    with pytest.raises(DatosNoValidos, match=fragmento):
        insertar_tarjeta(bd, replace(HF, **cambios))

    assert contar_por_banda(bd)["total"] == 0


def test_em410x_debe_tener_5_bytes(bd: BaseDatos) -> None:
    with pytest.raises(DatosNoValidos, match="debe tener 5 bytes"):
        insertar_tarjeta(bd, replace(LF, uid="0F03"))


def test_tipo_de_hf_en_banda_lf_no_es_valido(bd: BaseDatos) -> None:
    with pytest.raises(DatosNoValidos, match="no válido para LF"):
        insertar_tarjeta(bd, replace(LF, tipo="MIFARE Classic 1K"))


def test_se_informan_todos_los_errores_a_la_vez(bd: BaseDatos) -> None:
    with pytest.raises(DatosNoValidos) as error:
        insertar_tarjeta(bd, replace(HF, nombre="", uid="zz", tipo="otro"))

    assert len(error.value.errores) == 3
    assert str(error.value).startswith("Datos de la tarjeta no válidos:")


# ---------------------------------------------------------------- búsqueda


def _nombres(lista: list) -> list[str]:
    return [t.nombre for t in lista]


def test_listar_todas_mas_recientes_primero(bd: BaseDatos, con_tres: dict[str, int]) -> None:
    lista = listar(bd)

    assert _nombres(lista) == ["Pegatina 50%_descuento", "Tarjeta oficina", "Llavero portal"]
    assert all(t.salida == "" for t in lista)  # el listado no trae la salida completa


@pytest.mark.parametrize(
    ("texto", "esperados"),
    [
        ("oficina", ["Tarjeta oficina"]),
        ("OFICINA", ["Tarjeta oficina"]),
        ("congreso", ["Pegatina 50%_descuento"]),  # busca en las notas
        ("5a3e", ["Tarjeta oficina"]),  # UID sin espacios y en minúsculas
        ("3E 7C", ["Tarjeta oficina"]),  # UID con espacios
        ("0f0368", ["Llavero portal"]),
        ("50%", ["Pegatina 50%_descuento"]),  # '%' es texto, no comodín
        ("%", ["Pegatina 50%_descuento"]),
        ("_", ["Pegatina 50%_descuento"]),  # '_' es texto, no comodín
        ("no existe", []),
    ],
)
def test_listar_con_busqueda(bd: BaseDatos, con_tres: dict[str, int], texto: str, esperados: list[str]) -> None:
    assert _nombres(listar(bd, texto)) == esperados


def test_listar_por_banda(bd: BaseDatos, con_tres: dict[str, int]) -> None:
    assert _nombres(listar(bd, banda="lf")) == ["Llavero portal"]
    assert _nombres(listar(bd, "pegatina", banda="hf")) == ["Pegatina 50%_descuento"]
    assert _nombres(listar(bd, "pegatina", banda="lf")) == []


def test_listar_banda_no_valida(bd: BaseDatos) -> None:
    with pytest.raises(DatosNoValidos):
        listar(bd, banda="x' OR 1=1 --")


def test_obtener_trae_la_salida(bd: BaseDatos, con_tres: dict[str, int]) -> None:
    tarjeta = obtener(bd, con_tres["hf"])

    assert tarjeta is not None
    assert tarjeta.salida == "[+] UID: 5A 3E 7C 1B"
    assert obtener(bd, 9999) is None


def test_nombres_con_uid(bd: BaseDatos, con_tres: dict[str, int]) -> None:
    assert nombres_con_uid(bd, "5a3e7c1b") == ["Tarjeta oficina"]
    assert nombres_con_uid(bd, "00 00 00 00") == []
    assert nombres_con_uid(bd, "no es hex") == []


# ---------------------------------------------------------------- edición y borrado


def test_actualizar_nombre_y_notas(bd: BaseDatos, con_tres: dict[str, int]) -> None:
    assert actualizar(bd, con_tres["lf"], "  Portal casa  ", "nuevas notas")

    tarjeta = obtener(bd, con_tres["lf"])
    assert tarjeta is not None
    assert (tarjeta.nombre, tarjeta.notas) == ("Portal casa", "nuevas notas")
    assert tarjeta.uid == "0F 03 68 56 8B"  # lo demás no cambia


def test_actualizar_valida(bd: BaseDatos, con_tres: dict[str, int]) -> None:
    with pytest.raises(DatosNoValidos, match="nombre no puede estar vacío"):
        actualizar(bd, con_tres["lf"], "", "")
    with pytest.raises(DatosNoValidos, match="notas superan"):
        actualizar(bd, con_tres["lf"], "ok", "x" * (MAX_NOTAS + 1))

    tarjeta = obtener(bd, con_tres["lf"])
    assert tarjeta is not None and tarjeta.nombre == "Llavero portal"


def test_actualizar_tarjeta_inexistente(bd: BaseDatos) -> None:
    assert actualizar(bd, 9999, "x", "") is False


def test_borrar(bd: BaseDatos, con_tres: dict[str, int]) -> None:
    assert borrar(bd, con_tres["hf"])
    assert obtener(bd, con_tres["hf"]) is None
    assert borrar(bd, con_tres["hf"]) is False  # ya no existe
    assert contar_por_banda(bd)["total"] == 2
