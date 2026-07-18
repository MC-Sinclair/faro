"""Extrae metadatos de deprecación del docstring.

La librería ya sabe qué está obsoleto y lo declara con la directiva Sphinx
`.. deprecated::`. No lo deducimos: lo leemos.
"""

import re

from faro.dominio import Deprecacion

# `.. deprecated:: 2.0 <mensaje...>` — el mensaje puede seguir en líneas siguientes
# hasta una línea en blanco.
_DIRECTIVA = re.compile(
    r"^\s*\.\.\s+deprecated::\s*(?P<desde>\S+)\s*(?P<mensaje>.*?)(?=\n\s*\n|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Referencias cruzadas Sphinx: :meth:`_orm.Session.get` -> Session.get
# Capturamos las dos últimas componentes del target, que es como se nombra la API.
_XREF = re.compile(r":(?:meth|func|class|attr):`~?[\w.]*?(\w+\.\w+)`")


def extraer_deprecacion(doc: str | None) -> Deprecacion | None:
    """Devuelve la Deprecacion declarada en el docstring, o None si no hay."""
    if not doc:
        return None

    m = _DIRECTIVA.search(doc)
    if not m:
        return None

    mensaje = " ".join(m.group("mensaje").split())
    return Deprecacion(
        desde=m.group("desde"),
        mensaje=mensaje,
        reemplazo=_reemplazo_de(mensaje),
    )


def _reemplazo_de(mensaje: str) -> str | None:
    """El reemplazo sugerido, si la librería nombra uno.

    Heurística deliberadamente conservadora: tomamos la ÚLTIMA referencia cruzada
    del mensaje, que es donde las librerías suelen poner el "usá esto en su lugar"
    (la primera suele ser el propio símbolo deprecado). Si no hay ninguna, None.
    """
    refs = _XREF.findall(mensaje)
    if not refs:
        return None
    return refs[-1]
