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


class TipoTarjeta(StrEnum):
    """Tipo canónico de tarjeta: el mismo valor en parsers, recetas, BD, importación e interfaz.

    El valor se guarda en la base de datos y en los JSON exportados, así que no
    se debe cambiar: para un tipo nuevo se añade un miembro.
    """

    MIFARE_CLASSIC_1K = "MIFARE Classic 1K"
    MIFARE_CLASSIC_4K = "MIFARE Classic 4K"
    ULTRALIGHT_NTAG = "MIFARE Ultralight / NTAG"
    ISO14443A = "ISO14443-A"  # HF sin familia concreta
    EM410X = "EM410x"

    @property
    def banda(self) -> Banda:
        return Banda.LF if self is TipoTarjeta.EM410X else Banda.HF

    @classmethod
    def de_banda(cls, banda: Banda | str) -> frozenset[TipoTarjeta]:
        return frozenset(tipo for tipo in cls if tipo.banda == banda)


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
    tipo: TipoTarjeta


@dataclass(frozen=True)
class TarjetaLF:
    """Datos de 'lf search' (EM410x)."""

    id_em: str


@dataclass(frozen=True)
class Derivados:
    """Datos que se deducen del tipo y el UID (los genera siempre pm3/recetas.py)."""

    frecuencia: str
    tarjeta_destino: str
    seguridad: str
    comando_clonado: str
    comando_emulacion: str


@dataclass(frozen=True)
class TarjetaLeida:
    """Tarjeta leída, lista para mostrar y guardar."""

    fecha: str
    banda: Banda
    tipo: TipoTarjeta
    uid: str
    atqa: str
    sak: str
    salida: str
    derivados: Derivados


@dataclass(frozen=True)
class EstadoEmulacion:
    activa: bool
    comando: str | None = None
    salida: str = ""
