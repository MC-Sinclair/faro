"""Extractor de docstrings. Corre DENTRO del venv del proyecto objetivo.

CONTRATO: este archivo solo puede usar la stdlib. El venv del usuario no tiene
Faro instalado. No importar nada de `faro`.

Uso:
    python extractor.py '{"libreria": "sqlalchemy", "modulos": ["sqlalchemy.orm"]}'

Salida (stdout, JSON):
    {"version": "2.0.36", "simbolos": [{"nombre": "...", "doc": "..."}]}

No interpreta nada: vuelca docstrings crudos. El parseo de deprecaciones ocurre
del lado de Faro.
"""

import importlib
import importlib.metadata
import inspect
import json
import sys
import warnings


def version_de(libreria: str) -> str | None:
    """Versión exacta del paquete instalado, o None si no está.

    Los módulos de la stdlib (textwrap, json...) no son paquetes distribuidos y
    no tienen metadata: si importan, van con la versión de Python. Esto permite
    testear el extractor sin instalar nada.
    """
    try:
        return importlib.metadata.version(libreria)
    except importlib.metadata.PackageNotFoundError:
        pass

    try:
        importlib.import_module(libreria)
    except Exception:
        return None
    return ".".join(str(n) for n in sys.version_info[:3])


def extraer(modulos: list[str]) -> list[dict[str, str]]:
    vistos: dict[str, str] = {}

    for nombre_modulo in modulos:
        try:
            modulo = importlib.import_module(nombre_modulo)
        except Exception:
            # Un módulo que no importa no debe tumbar la extracción de los demás.
            continue

        for nombre, objeto in vars(modulo).items():
            if nombre.startswith("_"):
                continue

            if inspect.isclass(objeto):
                _anotar(vistos, f"{nombre_modulo}.{nombre}", objeto)
                for nombre_attr, attr in vars(objeto).items():
                    if nombre_attr.startswith("_"):
                        continue
                    if inspect.isfunction(attr) or isinstance(attr, property):
                        _anotar(
                            vistos,
                            f"{nombre_modulo}.{nombre}.{nombre_attr}",
                            attr,
                        )
            elif inspect.isfunction(objeto):
                _anotar(vistos, f"{nombre_modulo}.{nombre}", objeto)

    return [{"nombre": n, "doc": d} for n, d in sorted(vistos.items())]


def _anotar(vistos: dict[str, str], nombre: str, objeto: object) -> None:
    if nombre in vistos:
        return
    try:
        doc = inspect.getdoc(objeto)
    except Exception:
        return
    if doc:
        vistos[nombre] = doc


def main() -> None:
    warnings.filterwarnings("ignore")
    peticion = json.loads(sys.argv[1])

    libreria = peticion["libreria"]
    version = version_de(libreria)

    simbolos = extraer(peticion["modulos"]) if version is not None else []

    json.dump({"version": version, "simbolos": simbolos}, sys.stdout)


if __name__ == "__main__":
    main()
