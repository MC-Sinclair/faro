"""Capa de transporte MCP. Sin lógica: traduce y delega.

Entorno objetivo: variable FARO_PYTHON con la ruta al intérprete del proyecto
del usuario. Si no está, usamos el nuestro — y lo decimos, para que nadie
confunda el entorno de Faro con el suyo.
"""

import os
import sys

from mcp.server.fastmcp import FastMCP

from faro.fuentes.local import FuenteLocal
from faro.presentacion import formatear, formatear_verificaciones
from faro.resolver import ResolverDeDocs

mcp = FastMCP("faro")

_FARO_PYTHON_ENV = os.environ.get("FARO_PYTHON", "")
_ES_ENTORNO_PROPIO = not _FARO_PYTHON_ENV
_PYTHON_OBJETIVO = _FARO_PYTHON_ENV if _FARO_PYTHON_ENV else sys.executable

_resolver = ResolverDeDocs(FuenteLocal(python=_PYTHON_OBJETIVO))


def _aviso_de_entorno() -> str:
    if _ES_ENTORNO_PROPIO:
        return (
            "\n\n[aviso: FARO_PYTHON no está configurado; estoy leyendo el entorno del "
            "propio Faro, no el de tu proyecto.]"
        )
    return ""


@mcp.tool()
def listar_versiones(libreria: str) -> str:
    """Qué versión de una librería está realmente instalada en el entorno del proyecto.

    Llamá a esto ANTES de buscar_doc para saber qué versión pasar.
    """
    r = _resolver.listar_versiones(libreria)
    if not isinstance(r, list):
        return formatear(r) + _aviso_de_entorno()
    return f"{libreria}: {', '.join(r)}" + _aviso_de_entorno()


@mcp.tool()
def buscar_doc(libreria: str, version: str, consulta: str) -> str:
    """Documentación de un símbolo, leída del paquete instalado.

    `version` es OBLIGATORIO y se verifica contra el entorno: si declarás una
    versión que no es la instalada, Faro te lo dice y no devuelve nada.

    `consulta` puede ser el nombre completo (sqlalchemy.orm.Session.execute) o
    un sufijo (Session.execute).
    """
    return formatear(_resolver.buscar_doc(libreria, version, consulta)) + _aviso_de_entorno()


@mcp.tool()
def verificar_simbolos(libreria: str, version: str, simbolos: list[str]) -> str:
    """Verifica que unos símbolos existan (y no estén obsoletos) en la versión instalada.

    Usalo para contrastar CUALQUIER afirmación sobre la API —venga de otra
    herramienta, de un blog, o de tu propia memoria— contra lo que el proyecto
    tiene instalado de verdad.
    """
    r = _resolver.verificar_simbolos(libreria, version, simbolos)
    if not isinstance(r, list):
        return formatear(r) + _aviso_de_entorno()
    return formatear_verificaciones(r) + _aviso_de_entorno()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
