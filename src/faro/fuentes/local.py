"""Adaptador de producción: lee el paquete instalado en un venv objetivo.

Lanza un subproceso con el intérprete de ESE venv, que ejecuta extractor.py.
Dos razones: Faro puede leer cualquier entorno, y no importamos código de
terceros dentro del proceso del servidor.
"""

import json
import subprocess
from pathlib import Path

from faro.catalogo import CATALOGO
from faro.dominio import EntradaSimbolo
from faro.parseo import extraer_deprecacion

_EXTRACTOR = Path(__file__).parent / "extractor.py"
_TIMEOUT_SEG = 120


class FuenteLocal:
    def __init__(self, python: str) -> None:
        self._python = python
        self._cache: dict[str, dict] = {}

    def version_instalada(self, libreria: str) -> str | None:
        return self._extraer(libreria)["version"]

    def simbolos(self, libreria: str) -> list[EntradaSimbolo]:
        crudos = self._extraer(libreria)["simbolos"]
        return [
            EntradaSimbolo(
                nombre=s["nombre"],
                doc=s["doc"],
                firma=s.get("firma"),
                deprecacion=extraer_deprecacion(s["doc"]),
            )
            for s in crudos
        ]

    def _extraer(self, libreria: str) -> dict:
        if libreria in self._cache:
            return self._cache[libreria]

        entrada = CATALOGO.get(libreria)
        modulos = list(entrada.modulos) if entrada else None
        peticion = json.dumps({"libreria": libreria, "modulos": modulos})

        try:
            proc = subprocess.run(
                [self._python, str(_EXTRACTOR), peticion],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SEG,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(
                f"No pude ejecutar el intérprete '{self._python}': {e}. "
                f"Revisá la configuración del entorno objetivo (FARO_PYTHON)."
            ) from e

        if proc.returncode != 0:
            raise RuntimeError(
                f"El extractor falló con el intérprete '{self._python}': {proc.stderr}"
            )

        try:
            resultado = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"El extractor devolvió una salida no-JSON con el intérprete '{self._python}': "
                f"{e}. Salida cruda: {proc.stdout[:200]!r}"
            ) from e

        self._cache[libreria] = resultado
        return resultado
