"""Limpieza e interpretación de la salida del cliente de Iceman."""

from __future__ import annotations

import re

from pm3_dashboard.pm3.modelos import ResultadoComando

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# Textos que indican que el cliente no pudo hablar con la Proxmark3.
ERRORES_CONEXION = (
    "communicating with proxmark3 device failed",
    "cannot communicate",
    "could not open",
    "failed to open",
    "offline",
)


def limpiar_salida(texto: str | None) -> str:
    """Quita los colores ANSI y normaliza los saltos de línea a '\\n'."""
    return ANSI_RE.sub("", texto or "").replace("\r\n", "\n").replace("\r", "\n")


def hay_error_conexion(texto: str) -> bool:
    texto = texto.lower()
    return any(error in texto for error in ERRORES_CONEXION)


def interpretar_salida(codigo: int, stdout: str, stderr: str, puerto: str) -> ResultadoComando:
    """Convierte lo que devolvió el proceso en un ResultadoComando."""
    salida = limpiar_salida(stdout)
    error = limpiar_salida(stderr).strip()
    sin_conexion = hay_error_conexion(salida)
    ok = codigo == 0 and not sin_conexion
    if not ok and not error:
        error = (
            f"No se pudo comunicar con la Proxmark3 en {puerto}."
            if sin_conexion
            else f"El cliente terminó con código {codigo}."
        )
    return ResultadoComando(ok=ok, salida=salida, error=error, puerto=puerto)


# Causas frecuentes de fallo, reconocidas en la salida del cliente para dar un
# titular claro. La salida completa se muestra siempre; esto no la sustituye.
_DIAGNOSTICOS = (
    ("key.bin", "No se encontró el fichero de claves. «Leer bloques» recupera las claves "
                "automáticamente; vuelve a intentarlo."),
    ("can't find", "No se encontró el fichero de claves. «Leer bloques» recupera las claves "
                   "automáticamente; vuelve a intentarlo."),
    ("no tag found", "No se detectó ninguna tarjeta sobre la antena."),
    ("no known", "No se detectó ninguna tarjeta compatible sobre la antena."),
    ("authentication failed", "Fallo de autenticación: las claves no son válidas para esta tarjeta."),
    ("auth failed", "Fallo de autenticación: las claves no son válidas para esta tarjeta."),
)


def diagnostico_fallo(salida: str) -> str | None:
    """Mensaje claro para una causa frecuente encontrada en la salida, o None."""
    texto = (salida or "").lower()
    for fragmento, mensaje in _DIAGNOSTICOS:
        if fragmento in texto:
            return mensaje
    return None
