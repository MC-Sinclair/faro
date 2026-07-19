"""El núcleo de Faro.

No sabe qué es MCP. No sabe qué es un subproceso. No sabe qué es la red.
Habla con un puerto FuenteDeDocs y devuelve objetos de dominio.
"""

from faro.dominio import (
    Ambiguo,
    CandidatoDeprecado,
    EntradaSimbolo,
    Fragmento,
    NoEncontrado,
    Verificacion,
)
from faro.puertos import FuenteDeDocs


def version_compatible(pedida: str, instalada: str) -> bool:
    """¿La versión afirmada por el consumidor se corresponde con la instalada?

    Acepta prefijos de componente completo: "2.0" vale para "2.0.36".
    Rechaza prefijos de texto: "2.0" NO vale para "2.01.0".
    """
    if pedida == instalada:
        return True
    return instalada.startswith(pedida + ".")


class ResolverDeDocs:
    def __init__(self, fuente: FuenteDeDocs) -> None:
        self._fuente = fuente

    def listar_versiones(self, libreria: str) -> list[str] | NoEncontrado:
        instalada = self._fuente.version_instalada(libreria)
        if instalada is None:
            return NoEncontrado(
                motivo=f"'{libreria}' no está instalada en el entorno objetivo."
            )
        return [instalada]

    def buscar_doc(
        self, libreria: str, version: str, consulta: str
    ) -> Fragmento | Ambiguo | NoEncontrado:
        instalada = self._guarda_de_version(libreria, version)
        if isinstance(instalada, NoEncontrado):
            return instalada

        candidatos = _candidatos(consulta, self._fuente.simbolos(libreria))

        if not candidatos:
            return NoEncontrado(
                motivo=f"No hay ningún símbolo '{consulta}' en {libreria} {instalada}."
            )
        if len(candidatos) > 1:
            return Ambiguo(
                consulta=consulta,
                candidatos=sorted(e.nombre for e in candidatos),
                deprecados=_deprecados_de(candidatos),
            )

        entrada = candidatos[0]
        return Fragmento(
            libreria=libreria,
            version=instalada,
            simbolo=entrada.nombre,
            texto=entrada.doc,
            deprecacion=entrada.deprecacion,
            modulo_origen=entrada.modulo_origen,
            firma=entrada.firma,
        )

    def verificar_simbolos(
        self, libreria: str, version: str, simbolos: list[str]
    ) -> list[Verificacion] | NoEncontrado:
        """Contrasta afirmaciones sobre la API contra el paquete instalado.

        Las afirmaciones pueden venir de donde sea: otro MCP, un blog, o la
        memoria del propio modelo. Faro no pregunta de dónde salieron.
        """
        instalada = self._guarda_de_version(libreria, version)
        if isinstance(instalada, NoEncontrado):
            return instalada

        entradas = self._fuente.simbolos(libreria)
        veredictos: list[Verificacion] = []

        for simbolo in simbolos:
            candidatos = _candidatos(simbolo, entradas)

            if not candidatos:
                veredictos.append(
                    Verificacion(
                        simbolo=simbolo,
                        existe=False,
                        resuelto_como=None,
                        deprecacion=None,
                    )
                )
            elif len(candidatos) > 1:
                # Existe, pero no afirmamos a cuál resolvió: sería elegir por el
                # usuario. Sí decimos cuáles de las opciones están deprecadas: no
                # elegir no es lo mismo que ocultar que hay trampas entre ellas.
                veredictos.append(
                    Verificacion(
                        simbolo=simbolo,
                        existe=True,
                        resuelto_como=None,
                        deprecacion=None,
                        deprecados=_deprecados_de(candidatos),
                    )
                )
            else:
                e = candidatos[0]
                veredictos.append(
                    Verificacion(
                        simbolo=simbolo,
                        existe=True,
                        resuelto_como=e.nombre,
                        deprecacion=e.deprecacion,
                        firma=e.firma,
                        modulo_origen=e.modulo_origen,
                    )
                )

        return veredictos

    # --- helpers internos ---

    def _guarda_de_version(self, libreria: str, version: str) -> str | NoEncontrado:
        """Verifica la afirmación de versión del consumidor contra la realidad."""
        instalada = self._fuente.version_instalada(libreria)
        if instalada is None:
            return NoEncontrado(
                motivo=f"'{libreria}' no está instalada en el entorno objetivo."
            )
        if not version_compatible(version, instalada):
            return NoEncontrado(
                motivo=(
                    f"Pediste '{libreria}' {version}, pero el entorno tiene {instalada}. "
                    f"No sirvo doc de una versión que no es la tuya."
                )
            )
        return instalada


def _deprecados_de(entradas: list[EntradaSimbolo]) -> list[CandidatoDeprecado]:
    """Los candidatos que la librería declara obsoletos, en orden alfabético."""
    return [
        CandidatoDeprecado(nombre=e.nombre, deprecacion=e.deprecacion)
        for e in sorted(entradas, key=lambda e: e.nombre)
        if e.deprecacion is not None
    ]


def _candidatos(consulta: str, entradas: list[EntradaSimbolo]) -> list[EntradaSimbolo]:
    """Exacto primero; si no, por sufijo de componente. Sin matching difuso."""
    exactos = [e for e in entradas if e.nombre == consulta]
    if exactos:
        return exactos
    return [e for e in entradas if e.nombre.endswith("." + consulta)]
