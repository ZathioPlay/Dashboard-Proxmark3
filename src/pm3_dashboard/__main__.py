"""Punto de entrada: python -m pm3_dashboard."""

from __future__ import annotations

import webview

from pm3_dashboard.api import Api
from pm3_dashboard.paths import ruta_index

TITULO = "PM3 Dashboard"
ANCHO = 1280
ALTO = 800
TAMANO_MINIMO = (1024, 640)


def main() -> None:
    """Abre la ventana de la aplicación y carga la interfaz."""
    webview.create_window(
        TITULO,
        url=str(ruta_index()),
        js_api=Api(),
        width=ANCHO,
        height=ALTO,
        min_size=TAMANO_MINIMO,
        background_color="#06090f",
    )
    webview.start()


if __name__ == "__main__":
    main()
