"""Fuente de mentira para los tests. El núcleo se prueba sin red y sin subprocesos.

Los datos de prueba son REALES: salen del docstring verdadero de SQLAlchemy 2.0.36,
verificados contra el paquete. Un fake construido sobre suposiciones erróneas pasa
todos los tests mientras el producto falla — por eso además existen los tests de
contrato (Task 10).
"""

from faro.dominio import Deprecacion, EntradaSimbolo


class FuenteFake:
    def __init__(
        self, version: str | None, entradas: list[EntradaSimbolo], libreria: str = "sqlalchemy"
    ) -> None:
        self._version = version
        self._entradas = entradas
        self._libreria = libreria

    def version_instalada(self, libreria: str) -> str | None:
        return self._version if libreria == self._libreria else None

    def simbolos(self, libreria: str) -> list[EntradaSimbolo]:
        return list(self._entradas) if libreria == self._libreria else []


def simbolos_de_prueba() -> list[EntradaSimbolo]:
    """Un puñado de símbolos reales de SQLAlchemy 2.0.36."""
    return [
        EntradaSimbolo(
            nombre="sqlalchemy.orm.Session.execute",
            doc="Execute a SQL expression construct.",
            deprecacion=None,
            firma="(statement, params=None, *, execution_options={})",
        ),
        EntradaSimbolo(
            nombre="sqlalchemy.orm.Session.get",
            doc="Return an instance based on the given primary key identifier.",
            deprecacion=None,
        ),
        EntradaSimbolo(
            nombre="sqlalchemy.orm.Query.get",
            doc="Return an instance based on the given primary key identifier, or None if not found.",
            deprecacion=Deprecacion(
                desde="2.0",
                mensaje=(
                    "The Query.get method is considered legacy as of the 1.x series of "
                    "SQLAlchemy and becomes a legacy construct in 2.0. The method is now "
                    "available as Session.get"
                ),
                reemplazo="Session.get",
            ),
        ),
        # Dos símbolos que colisionan por sufijo: fuerzan el camino Ambiguo.
        EntradaSimbolo(
            nombre="sqlalchemy.sql.expression.Select.select",
            doc="Legacy select.",
            deprecacion=None,
        ),
        EntradaSimbolo(
            nombre="sqlalchemy.schema.Table.select",
            doc="Return a SELECT of this Table.",
            deprecacion=None,
        ),
    ]
