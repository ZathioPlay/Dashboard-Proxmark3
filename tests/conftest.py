"""Configuración común de pytest."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def appdata_temporal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirige %APPDATA% a una carpeta temporal para no tocar los datos reales."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path
