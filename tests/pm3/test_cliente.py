"""Tests de ClientePm3 con un lanzador falso (nunca se usa la Proxmark real)."""

from __future__ import annotations

import threading
from pathlib import Path

from pm3_dashboard.config import ConfigPm3
from pm3_dashboard.pm3.cliente import (
    MSG_OCUPADA,
    MSG_TIEMPO_AGOTADO,
    ClientePm3,
    TiempoAgotado,
    construir_entorno,
)
from tests.pm3.falsos import LanzadorFalso, cargar_muestra


def test_monta_la_llamada_al_cliente(cliente: ClientePm3, lanzador: LanzadorFalso, ejecutable: Path) -> None:
    lanzador.responder("hw version", stdout=cargar_muestra("hw_version"))

    resultado = cliente.ejecutar("hw version")

    assert resultado.ok
    assert resultado.puerto == "COM5"
    assert "RRG/Iceman" in resultado.salida
    assert lanzador.llamadas == [[str(ejecutable), "-p", "COM5", "-c", "hw version"]]


def test_limpia_colores_y_saltos_de_linea(cliente: ClientePm3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hw tune", stdout="\x1b[32m[+]\x1b[0m linea 1\r\nlinea 2\r")

    assert cliente.ejecutar("hw tune").salida == "[+] linea 1\nlinea 2\n"


def test_error_de_conexion_aunque_el_codigo_sea_cero(cliente: ClientePm3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hw version", stdout=cargar_muestra("sin_conexion"), codigo=0)

    resultado = cliente.ejecutar("hw version")

    assert not resultado.ok
    assert resultado.error == "No se pudo comunicar con la Proxmark3 en COM5."


def test_codigo_de_salida_distinto_de_cero(cliente: ClientePm3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hw tune", codigo=3)

    resultado = cliente.ejecutar("hw tune")

    assert not resultado.ok
    assert resultado.error == "El cliente terminó con código 3."


def test_stderr_se_usa_como_mensaje_de_error(cliente: ClientePm3, lanzador: LanzadorFalso) -> None:
    lanzador.responder("hw tune", codigo=1, stderr="algo fue mal\n")

    assert cliente.ejecutar("hw tune").error == "algo fue mal"


def test_tiempo_agotado(cliente: ClientePm3, lanzador: LanzadorFalso) -> None:
    lanzador.fallar("hw tune", TiempoAgotado())

    resultado = cliente.ejecutar("hw tune")

    assert not resultado.ok
    assert resultado.error == MSG_TIEMPO_AGOTADO


def test_cliente_que_no_se_puede_ejecutar(cliente: ClientePm3, lanzador: LanzadorFalso) -> None:
    lanzador.fallar("hw tune", FileNotFoundError())

    assert "No se pudo ejecutar el cliente de Iceman" in cliente.ejecutar("hw tune").error


def test_cliente_inexistente_no_lanza_nada(lanzador: LanzadorFalso, tmp_path: Path) -> None:
    config = ConfigPm3(ruta_cliente=str(tmp_path / "no_existe.exe"), puerto="COM5")
    cliente = ClientePm3(cargar=lambda: config, lanzador=lanzador, carpeta_trabajo=tmp_path)

    resultado = cliente.ejecutar("hw version")

    assert not resultado.ok
    assert "No se encuentra el cliente de Iceman" in resultado.error
    assert lanzador.llamadas == []


def test_sin_proxmark_conectada(config: ConfigPm3, lanzador: LanzadorFalso, tmp_path: Path) -> None:
    cliente = ClientePm3(
        cargar=lambda: config, lanzador=lanzador, detectar=lambda _: None, carpeta_trabajo=tmp_path
    )

    resultado = cliente.ejecutar("hw version")

    assert not resultado.ok
    assert "No se detecta ninguna Proxmark3" in resultado.error
    assert lanzador.llamadas == []


def test_un_solo_comando_a_la_vez(cliente: ClientePm3, lanzador: LanzadorFalso) -> None:
    lanzador.bloqueo = threading.Event()
    resultados = {}
    primero = threading.Thread(target=lambda: resultados.setdefault("hw tune", cliente.ejecutar("hw tune", timeout=5)))
    primero.start()
    assert lanzador.dentro.wait(2), "el primer comando no llegó a lanzarse"

    segundo = cliente.ejecutar("hw version", timeout=0.1)

    assert not segundo.ok
    assert segundo.error == MSG_OCUPADA
    lanzador.bloqueo.set()
    primero.join(2)
    assert resultados["hw tune"].ok
    assert lanzador.comandos == ["hw tune"]  # el segundo nunca llegó al puerto


def test_entorno_incluye_dlls_del_cliente(tmp_path: Path) -> None:
    cliente = tmp_path / "client" / "proxmark3.exe"
    (cliente.parent / "libs").mkdir(parents=True)
    extra = tmp_path / "msys2"

    env = construir_entorno(cliente, [extra], {"PATH": "C:\\Windows"})

    rutas = env["PATH"].split(";" if ";" in env["PATH"] else ":")
    assert rutas[0] == str(cliente.parent)
    assert str(cliente.parent / "libs") in rutas
    assert str(extra) in rutas
    assert rutas[-1] == "C:\\Windows"
    assert env["QT_PLUGIN_PATH"] == str(cliente.parent / "libs")
