"""Fixtures de storage: siempre una base de datos temporal."""

from __future__ import annotations

from pathlib import Path

import pytest

from pm3_dashboard.storage import BaseDatos


@pytest.fixture
def bd(tmp_path: Path) -> BaseDatos:
    return BaseDatos(tmp_path / "pm3.db")
