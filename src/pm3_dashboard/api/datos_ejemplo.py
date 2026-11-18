"""Datos de ejemplo para la fase 1. Se eliminará cuando haya datos reales (fase 3)."""

from __future__ import annotations

from typing import Any


def resumen_ejemplo() -> dict[str, Any]:
    """Resumen con la misma forma que tendrá el resumen real."""
    return {
        "es_ejemplo": True,
        "dispositivo": {
            "conectado": True,
            "puerto": "COM5",
            "firmware": "Iceman/master/v4.20728",
            "cliente": "proxmark3.exe",
        },
        "tarjetas": {
            "total": 12,
            "hf": 8,
            "lf": 4,
        },
        "antenas": {
            "fecha": "2026-11-18 10:42",
            "lf": {"voltios": 34.2, "optimo": 20.0, "ok": True},
            "hf": {"voltios": 26.8, "optimo": 18.0, "ok": True},
        },
        "actividad": [
            {
                "fecha": "2026-11-18 10:45",
                "tipo": "lectura",
                "descripcion": "MIFARE Classic 1K leída (UID 04A1B2C3)",
            },
            {
                "fecha": "2026-11-18 10:42",
                "tipo": "antenas",
                "descripcion": "Medición de antenas: LF 34.2 V, HF 26.8 V",
            },
            {
                "fecha": "2026-11-17 18:10",
                "tipo": "guardado",
                "descripcion": "EM4100 guardada en la base de datos como «Llavero portal»",
            },
            {
                "fecha": "2026-11-17 18:02",
                "tipo": "emulacion",
                "descripcion": "Emulación de EM4100 durante 30 s",
            },
            {
                "fecha": "2026-11-17 17:55",
                "tipo": "conexion",
                "descripcion": "Proxmark3 detectada en COM5",
            },
        ],
    }
