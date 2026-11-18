"""Tests del LanzadorSubprocess real, lanzando Python en lugar de proxmark3.exe."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from pm3_dashboard.pm3.cliente import LanzadorSubprocess, SesionProceso, TiempoAgotado
from tests.pm3.falsos import esperar_hasta


def test_ejecutar_captura_salida_y_codigo(tmp_path: Path) -> None:
    codigo = "import sys; print('hola'); print('error', file=sys.stderr); sys.exit(2)"

    salida = LanzadorSubprocess().ejecutar(
        [sys.executable, "-c", codigo], timeout=10, env=os.environ, cwd=tmp_path
    )

    assert salida.codigo == 2
    assert salida.stdout.strip() == "hola"
    assert salida.stderr.strip() == "error"


def test_ejecutar_con_tiempo_agotado(tmp_path: Path) -> None:
    with pytest.raises(TiempoAgotado):
        LanzadorSubprocess().ejecutar(
            [sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.5, env=os.environ, cwd=tmp_path
        )


def test_sesion_real_se_detiene(tmp_path: Path) -> None:
    codigo = "import time\nprint('simulando', flush=True)\nwhile True: time.sleep(0.1)"
    proceso = LanzadorSubprocess().abrir([sys.executable, "-c", codigo], env=os.environ, cwd=tmp_path)
    liberado = []
    sesion = SesionProceso(proceso, "COM5", al_terminar=lambda: liberado.append(True))

    assert esperar_hasta(lambda: "simulando" in sesion.salida(), limite=10)
    sesion.detener()

    assert proceso.poll() is not None
    assert liberado == [True]  # el puerto se libera una sola vez
