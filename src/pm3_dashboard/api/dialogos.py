"""Diálogos nativos de abrir/guardar archivo (separados para sustituirlos en los tests)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import webview

TIPOS_JSON = ("Archivos JSON (*.json)", "Todos los archivos (*.*)")


class Dialogos(Protocol):
    def elegir_guardar(self, nombre_sugerido: str) -> Path | None: ...
    def elegir_abrir(self) -> Path | None: ...


def _primera_ruta(resultado: str | Sequence[str] | None) -> Path | None:
    """pywebview devuelve una tupla de rutas (o una cadena en algunos sistemas); None = cancelado."""
    if not resultado:
        return None
    if isinstance(resultado, str):
        return Path(resultado)
    return Path(resultado[0])


class DialogosPywebview:
    """Usa la ventana activa de pywebview. Se llama desde el hilo de la Api, nunca desde el de la ventana."""

    def _ventana(self) -> webview.Window:
        import webview

        ventana = webview.active_window() or (webview.windows[0] if webview.windows else None)
        if ventana is None:
            raise RuntimeError("No hay ninguna ventana abierta para mostrar el diálogo.")
        return ventana

    def elegir_guardar(self, nombre_sugerido: str) -> Path | None:
        import webview

        return _primera_ruta(
            self._ventana().create_file_dialog(
                webview.FileDialog.SAVE, save_filename=nombre_sugerido, file_types=TIPOS_JSON
            )
        )

    def elegir_abrir(self) -> Path | None:
        import webview

        return _primera_ruta(self._ventana().create_file_dialog(webview.FileDialog.OPEN, file_types=TIPOS_JSON))
