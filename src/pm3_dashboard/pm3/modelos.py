"""Tipos de datos que devuelve el paquete pm3 (sin lógica).

Todos son dataclasses que se pueden convertir con dataclasses.asdict() y
serializar a JSON (los StrEnum se serializan como texto).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

T = TypeVar("T")


class Banda(StrEnum):
    HF = "hf"
    LF = "lf"


class EstadoAntena(StrEnum):
    OK = "OK"
    MARGINAL = "MARGINAL"
    INUTILIZABLE = "INUTILIZABLE"
    BAJA = "BAJA"
    SIN_DATOS = "SIN DATOS"


class FamiliaHF(StrEnum):
    """Familias de tarjetas HF que se distinguen. El valor es el texto que se muestra."""

    MIFARE_CLASSIC_1K = "MIFARE Classic 1K"
    MIFARE_CLASSIC_4K = "MIFARE Classic 4K"
    ULTRALIGHT_NTAG = "MIFARE Ultralight / NTAG"
    DESCONOCIDA = "ISO14443-A (HF)"


@dataclass(frozen=True)
class ResultadoComando:
    """Resultado de lanzar un comando con el cliente de Iceman."""

    ok: bool
    salida: str = ""
    error: str = ""
    puerto: str | None = None


@dataclass(frozen=True)
class Respuesta(Generic[T]):
    """Resultado de una operación de alto nivel (estado, antenas, lectura...)."""

    ok: bool
    datos: T | None = None
    error: str = ""
    salida: str = ""
    puerto: str | None = None


@dataclass(frozen=True)
class InfoVersion:
    """Datos de 'hw version'."""

    cliente: str = ""
    firmware: str = ""
    bootrom: str = ""
    dispositivo: str = ""
    # None si falta alguna de las dos versiones para comparar.
    versiones_coinciden: bool | None = None


@dataclass(frozen=True)
class MedicionAntena:
    voltios: float | None
    estado: EstadoAntena


@dataclass(frozen=True)
class MedicionAntenas:
    """Datos de 'hw tune'."""

    lf: MedicionAntena
    hf: MedicionAntena


@dataclass(frozen=True)
class TarjetaHF:
    """Datos de 'hf search'."""

    uid: str
    atqa: str | None
    sak: str | None
    familia: FamiliaHF


@dataclass(frozen=True)
class TarjetaLF:
    """Datos de 'lf search' (EM410x)."""

    id_em: str


@dataclass(frozen=True)
class TarjetaLeida:
    """Tarjeta lista para mostrar y guardar, con sus comandos de clonado y emulación."""

    fecha: str
    frecuencia: str
    banda: Banda
    tipo: str
    uid: str
    atqa: str
    sak: str
    tarjeta_destino: str
    seguridad: str
    comando_clonado: str
    comando_emulacion: str
    salida: str


@dataclass(frozen=True)
class EstadoEmulacion:
    activa: bool
    comando: str | None = None
    salida: str = ""
