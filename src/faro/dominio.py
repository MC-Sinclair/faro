"""Modelo de dominio de Faro.

La cita no es un formato de salida: es una propiedad estructural. Un Fragmento
no puede existir sin decir de dónde salió (regla 2).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Deprecacion:
    """Lo que la propia librería declara sobre un símbolo obsoleto."""

    desde: str
    mensaje: str
    reemplazo: str | None


@dataclass(frozen=True)
class EntradaSimbolo:
    """Un símbolo tal como lo devuelve una FuenteDeDocs, sin interpretar."""

    nombre: str
    doc: str
    deprecacion: Deprecacion | None
    firma: str | None = None


@dataclass(frozen=True)
class Fragmento:
    """Una respuesta de Faro. Lleva su procedencia dentro."""

    libreria: str
    version: str
    simbolo: str
    texto: str
    deprecacion: Deprecacion | None
    firma: str | None = None


@dataclass(frozen=True)
class Ambiguo:
    """La consulta resuelve a varios símbolos. Faro no elige por el usuario."""

    consulta: str
    candidatos: list[str]


@dataclass(frozen=True)
class NoEncontrado:
    """El 'no lo tengo' honesto de la regla 3. Nunca mudo: siempre con motivo."""

    motivo: str


@dataclass(frozen=True)
class Verificacion:
    """El veredicto sobre un símbolo afirmado por alguien (modelo, blog, otro MCP)."""

    simbolo: str
    existe: bool
    resuelto_como: str | None
    deprecacion: Deprecacion | None
    firma: str | None = None
