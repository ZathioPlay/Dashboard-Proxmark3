"""Tests de la emulación con un proceso falso que no termina hasta que se detiene."""

from __future__ import annotations

import pytest

from pm3_dashboard.pm3.cliente import MSG_EMULACION, ClientePm3
from pm3_dashboard.pm3.emulacion import GestorEmulacion, validar_comando_emulacion
from tests.pm3.falsos import LanzadorFalso, esperar_hasta

COMANDO = "lf em 410x sim --id 0F0368568B"


@pytest.fixture
def gestor(cliente: ClientePm3) -> GestorEmulacion:
    return GestorEmulacion(cliente, espera_inicial=0)


@pytest.mark.parametrize("comando", ["lf em 410x sim --id 0F0368568B", "hf mf sim --1k -u 5A3E7C1B"])
def test_comandos_de_simulacion_validos(comando: str) -> None:
    assert validar_comando_emulacion(comando) is None


@pytest.mark.parametrize(
    "comando",
    [
        "hw tune",
        "lf em 410x clone --id 0F0368568B",
        "hf mf wrbl --blk 0",
        "lf em 410x sim --id 0F0368568B; lf t55xx wipe",
        "lf em 410x sim --id 0F0368568B\nlf t55xx wipe",
    ],
)
def test_comandos_rechazados(gestor: GestorEmulacion, lanzador: LanzadorFalso, comando: str) -> None:
    respuesta = gestor.iniciar(comando)

    assert not respuesta.ok
    assert lanzador.llamadas == []


def test_iniciar_consultar_y_detener(gestor: GestorEmulacion, lanzador: LanzadorFalso) -> None:
    respuesta = gestor.iniciar(COMANDO)

    assert respuesta.ok
    assert respuesta.puerto == "COM5"
    assert lanzador.comandos == [COMANDO]
    proceso = lanzador.procesos[0]
    proceso.stdout.escribir("[#] Simulating EM410x\n")
    assert esperar_hasta(lambda: "Simulating" in gestor.estado().salida)
    estado = gestor.estado()
    assert estado.activa
    assert estado.comando == COMANDO

    parada = gestor.detener()

    assert parada.ok
    assert proceso.terminate_llamado
    assert not gestor.estado().activa
    assert "Simulating EM410x" in parada.salida
    assert lanzador.comandos == [COMANDO, "hw break"]  # se manda parar al firmware


def test_no_permite_otro_comando_mientras_emula(
    gestor: GestorEmulacion, cliente: ClientePm3, lanzador: LanzadorFalso
) -> None:
    gestor.iniciar(COMANDO)

    resultado = cliente.ejecutar("hw tune")

    assert not resultado.ok
    assert resultado.error == MSG_EMULACION
    assert lanzador.comandos == [COMANDO]


def test_no_permite_dos_emulaciones(gestor: GestorEmulacion, lanzador: LanzadorFalso) -> None:
    gestor.iniciar(COMANDO)

    segunda = gestor.iniciar("hf mf sim --1k -u 5A3E7C1B")

    assert not segunda.ok
    assert "Ya hay una emulación en curso" in segunda.error
    assert len(lanzador.procesos) == 1


def test_detener_libera_el_puerto(gestor: GestorEmulacion, cliente: ClientePm3, lanzador: LanzadorFalso) -> None:
    gestor.iniciar(COMANDO)
    gestor.detener()

    assert cliente.ejecutar("hw version", timeout=0.5).ok


def test_si_el_proceso_termina_solo_se_libera_el_puerto(
    gestor: GestorEmulacion, cliente: ClientePm3, lanzador: LanzadorFalso
) -> None:
    gestor.iniciar(COMANDO)

    lanzador.procesos[0].terminar_solo()

    assert esperar_hasta(lambda: not gestor.estado().activa)
    assert cliente.ejecutar("hw version", timeout=0.5).ok
    assert gestor.estado().comando == COMANDO  # se conserva para mostrar qué terminó


def test_proceso_que_no_responde_se_mata(cliente: ClientePm3, lanzador: LanzadorFalso) -> None:
    lanzador.ignora_terminate = True
    sesion = cliente.abrir_sesion(COMANDO)

    sesion.detener(espera=0.05)

    proceso = lanzador.procesos[0]
    assert proceso.terminate_llamado
    assert proceso.kill_llamado
    assert sesion.terminada
    assert cliente.ejecutar("hw version", timeout=0.5).ok


def test_detener_sin_emulacion(gestor: GestorEmulacion, lanzador: LanzadorFalso) -> None:
    respuesta = gestor.detener()

    assert respuesta.ok
    assert respuesta.salida == "No había ninguna emulación activa."
    assert lanzador.llamadas == []


def test_error_al_lanzar_libera_el_puerto(
    gestor: GestorEmulacion, cliente: ClientePm3, lanzador: LanzadorFalso
) -> None:
    lanzador.error_al_abrir = OSError("acceso denegado")

    respuesta = gestor.iniciar(COMANDO)

    assert not respuesta.ok
    assert "acceso denegado" in respuesta.error
    assert not gestor.estado().activa
    assert cliente.ejecutar("hw version", timeout=0.5).ok


def test_se_guardan_como_maximo_500_lineas(gestor: GestorEmulacion, lanzador: LanzadorFalso) -> None:
    gestor.iniciar(COMANDO)
    proceso = lanzador.procesos[0]
    for numero in range(600):
        proceso.stdout.escribir(f"linea {numero}\n")

    assert esperar_hasta(lambda: "linea 599" in gestor.estado().salida)
    lineas = gestor.estado().salida.splitlines()
    assert len(lineas) == 500
    assert lineas[0] == "linea 100"
    gestor.detener()
