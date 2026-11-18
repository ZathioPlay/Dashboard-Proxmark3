"""Clase expuesta a JavaScript como window.pywebview.api.

Cada método público se puede llamar desde la interfaz y devuelve datos
serializables a JSON (dict, list, str, int, float, bool, None).
"""

from __future__ import annotations

from typing import Any

from pm3_dashboard.api import datos_ejemplo


class Api:
    """Puente entre la interfaz y la lógica de la aplicación."""

    def obtener_resumen(self) -> dict[str, Any]:
        """Datos para la pantalla de inicio (dashboard).

        En la fase 1 devuelve datos de ejemplo; en la fase 3 se obtendrán de
        la Proxmark3 (pm3/) y de la base de datos (storage/).
        """
        return datos_ejemplo.resumen_ejemplo()
