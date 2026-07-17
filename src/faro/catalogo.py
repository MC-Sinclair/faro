"""Qué librerías conoce Faro. Data, no código.

Agregar FastAPI mañana es agregar una entrada acá. El núcleo no se toca.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EntradaCatalogo:
    nombre: str
    modulos: tuple[str, ...]


CATALOGO: dict[str, EntradaCatalogo] = {
    "sqlalchemy": EntradaCatalogo(
        nombre="sqlalchemy",
        modulos=(
            "sqlalchemy",
            "sqlalchemy.orm",
            "sqlalchemy.sql.expression",
            "sqlalchemy.engine",
            "sqlalchemy.schema",
            "sqlalchemy.types",
            "sqlalchemy.exc",
            "sqlalchemy.pool",
            "sqlalchemy.event",
            "sqlalchemy.ext.asyncio",
            "sqlalchemy.ext.hybrid",
        ),
    ),
}
