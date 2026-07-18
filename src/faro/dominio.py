"""Modelo de dominio de Faro.

La cita no es un formato de salida: es una propiedad estructural. Un Fragmento
no puede existir sin decir de dónde salió (regla 2).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Deprecacion:
    """Lo que la propia librería declara sobre un símbolo obsoleto."""

    desde: str
    mensaje: str
    reemplazo: str | None


@dataclass(frozen=True)
class CandidatoDeprecado:
    """Un candidato de una consulta ambigua que además está deprecado.

    Distinto de `Deprecacion` a secas: acá el nombre importa, porque son varios
    y cada uno puede declarar su propio reemplazo. Faro los nombra a todos en
    vez de elegir uno.
    """

    nombre: str
    deprecacion: Deprecacion


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
    """La consulta resuelve a varios símbolos. Faro no elige por el usuario.

    `deprecados` es el subconjunto de candidatos que la librería declara
    obsoletos: no elegir por el usuario no es lo mismo que ocultarle que
    algunas de las opciones son trampas.
    """

    consulta: str
    candidatos: list[str]
    deprecados: list[CandidatoDeprecado] = field(default_factory=list)


@dataclass(frozen=True)
class NoEncontrado:
    """El 'no lo tengo' honesto de la regla 3. Nunca mudo: siempre con motivo."""

    motivo: str


@dataclass(frozen=True)
class Verificacion:
    """El veredicto sobre un símbolo afirmado por alguien (modelo, blog, otro MCP).

    `deprecacion` (singular) es "el símbolo que pediste, resuelto sin ambigüedad,
    está deprecado". `deprecados` (plural) es "algunas de las varias cosas que tu
    consulta podría significar lo están" — situaciones distintas, y en la segunda
    puede haber varios reemplazos, así que colapsarlas obligaría a elegir uno.
    """

    simbolo: str
    existe: bool
    resuelto_como: str | None
    deprecacion: Deprecacion | None
    firma: str | None = None
    deprecados: list[CandidatoDeprecado] = field(default_factory=list)
