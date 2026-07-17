"""Los puertos del núcleo.

El núcleo habla con esto, nunca con un subproceso ni con la red. Cambiar de
fuente (paquete instalado -> web) es escribir otro adaptador, no tocar el resolver.
"""

from typing import Protocol

from faro.dominio import EntradaSimbolo


class FuenteDeDocs(Protocol):
    def version_instalada(self, libreria: str) -> str | None:
        """La versión exacta instalada, o None si la librería no está."""
        ...

    def simbolos(self, libreria: str) -> list[EntradaSimbolo]:
        """Todos los símbolos documentados de esa librería, ya parseados."""
        ...
