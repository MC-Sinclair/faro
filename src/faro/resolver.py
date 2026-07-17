"""El núcleo de Faro.

No sabe qué es MCP. No sabe qué es un subproceso. No sabe qué es la red.
Habla con un puerto FuenteDeDocs y devuelve objetos de dominio.
"""

from faro.catalogo import CATALOGO, EntradaCatalogo
from faro.dominio import NoEncontrado
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
