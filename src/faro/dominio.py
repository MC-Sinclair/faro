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
    """Un símbolo tal como lo devuelve una FuenteDeDocs, sin interpretar.

    `doc` puede ser None: hay símbolos que existen y no declaran documentación.
    No tener doc no es no existir. `modulo_origen` es la raíz de __module__ del
    objeto: la librería que REALMENTE lo define, que puede no ser la librería
    consultada (p. ej. pathlib.Path importado dentro de otro paquete).
    """

    nombre: str
    doc: str | None
    deprecacion: Deprecacion | None
    modulo_origen: str
    firma: str | None = None


@dataclass(frozen=True)
class Fragmento:
    """Una respuesta de Faro. Lleva su procedencia dentro.

    `texto` puede ser None (símbolo sin documentación declarada) — no debilita la
    regla 2: la garantía estructural es sobre libreria/version/simbolo, y `texto`
    sigue siendo obligatorio de construir, solo que su valor puede ser nulo.
    `modulo_origen` es la librería que REALMENTE define `simbolo` (raíz de
    __module__): puede ser distinta de `libreria` cuando el símbolo solo está
    importado ahí, no definido (p. ej. pathlib.Path dentro de otro paquete). Es
    obligatorio, igual que libreria/version/simbolo: nunca hay Fragmento sin
    saber de dónde sale de verdad el símbolo.
    """

    libreria: str
    version: str
    simbolo: str
    texto: str | None
    deprecacion: Deprecacion | None
    modulo_origen: str
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
    `modulo_origen` sigue el mismo patrón que `firma`/`resuelto_como`: solo tiene
    sentido cuando la consulta resolvió a un único símbolo, así que es None en
    los casos "no existe" y "ambiguo" (no hay un origen único que afirmar).
    """

    simbolo: str
    existe: bool
    resuelto_como: str | None
    deprecacion: Deprecacion | None
    firma: str | None = None
    modulo_origen: str | None = None
    deprecados: list[CandidatoDeprecado] = field(default_factory=list)
