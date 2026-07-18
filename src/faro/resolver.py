"""El núcleo de Faro.

No sabe qué es MCP. No sabe qué es un subproceso. No sabe qué es la red.
Habla con un puerto FuenteDeDocs y devuelve objetos de dominio.
"""

from faro.catalogo import CATALOGO, EntradaCatalogo
from faro.dominio import Ambiguo, EntradaSimbolo, Fragmento, NoEncontrado, Verificacion
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
    def __init__(
        self,
        fuente: FuenteDeDocs,
        catalogo: dict[str, EntradaCatalogo] | None = None,
    ) -> None:
        self._fuente = fuente
        self._catalogo = catalogo if catalogo is not None else CATALOGO

    def listar_versiones(self, libreria: str) -> list[str] | NoEncontrado:
        conocida = self._verificar_catalogo(libreria)
        if isinstance(conocida, NoEncontrado):
            return conocida

        instalada = self._fuente.version_instalada(libreria)
        if instalada is None:
            return NoEncontrado(
                motivo=f"'{libreria}' no está instalada en el entorno objetivo."
            )
        return [instalada]

    def buscar_doc(
        self, libreria: str, version: str, consulta: str
    ) -> Fragmento | Ambiguo | NoEncontrado:
        conocida = self._verificar_catalogo(libreria)
        if isinstance(conocida, NoEncontrado):
            return conocida

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
            )

        entrada = candidatos[0]
        return Fragmento(
            libreria=libreria,
            version=instalada,
            simbolo=entrada.nombre,
            texto=entrada.doc,
            deprecacion=entrada.deprecacion,
            firma=entrada.firma,
        )

    def verificar_simbolos(
        self, libreria: str, version: str, simbolos: list[str]
    ) -> list[Verificacion] | NoEncontrado:
        """Contrasta afirmaciones sobre la API contra el paquete instalado.

        Las afirmaciones pueden venir de donde sea: otro MCP, un blog, o la
        memoria del propio modelo. Faro no pregunta de dónde salieron.
        """
        conocida = self._verificar_catalogo(libreria)
        if isinstance(conocida, NoEncontrado):
            return conocida

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
                # Existe, pero no afirmamos a cuál resolvió: sería elegir por el usuario.
                veredictos.append(
                    Verificacion(
                        simbolo=simbolo,
                        existe=True,
                        resuelto_como=None,
                        deprecacion=None,
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
                    )
                )

        return veredictos

    # --- helpers internos ---

    def _verificar_catalogo(self, libreria: str) -> None | NoEncontrado:
        if libreria in self._catalogo:
            return None
        conocidas = ", ".join(sorted(self._catalogo))
        return NoEncontrado(
            motivo=f"No conozco '{libreria}'. Librerías que conozco: {conocidas}."
        )

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


def _candidatos(consulta: str, entradas: list[EntradaSimbolo]) -> list[EntradaSimbolo]:
    """Exacto primero; si no, por sufijo de componente. Sin matching difuso."""
    exactos = [e for e in entradas if e.nombre == consulta]
    if exactos:
        return exactos
    return [e for e in entradas if e.nombre.endswith("." + consulta)]
