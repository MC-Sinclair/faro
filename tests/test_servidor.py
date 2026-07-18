"""Tests del manejo de FARO_PYTHON en el módulo de transporte MCP.

Alcance deliberadamente chico: solo la lógica de "¿qué intérprete uso, y es el
propio de Faro o el del proyecto objetivo?", calculada una vez al importar el
módulo. No es una suite general de servidor.py — eso queda fuera de foco.
"""

import importlib
import sys

import faro.servidor


def test_faro_python_vacio_se_trata_como_no_configurado(monkeypatch):
    """Regresión: `.mcp.json` puede expandir FARO_PYTHON="" cuando el host no
    la tiene seteada. Antes, el chequeo era de presencia ("FARO_PYTHON" not in
    os.environ), así que un string vacío quedaba marcado como "configurado" y
    _PYTHON_OBJETIVO terminaba siendo "" en vez de caer al propio intérprete.
    """
    monkeypatch.setenv("FARO_PYTHON", "")
    importlib.reload(faro.servidor)
    try:
        assert faro.servidor._ES_ENTORNO_PROPIO is True
        assert faro.servidor._PYTHON_OBJETIVO == sys.executable
    finally:
        importlib.reload(faro.servidor)


def test_faro_python_no_seteado_es_entorno_propio(monkeypatch):
    monkeypatch.delenv("FARO_PYTHON", raising=False)
    importlib.reload(faro.servidor)
    try:
        assert faro.servidor._ES_ENTORNO_PROPIO is True
        assert faro.servidor._PYTHON_OBJETIVO == sys.executable
    finally:
        importlib.reload(faro.servidor)


def test_faro_python_con_ruta_real_no_es_entorno_propio(monkeypatch):
    monkeypatch.setenv("FARO_PYTHON", sys.executable)
    importlib.reload(faro.servidor)
    try:
        assert faro.servidor._ES_ENTORNO_PROPIO is False
        assert faro.servidor._PYTHON_OBJETIVO == sys.executable
    finally:
        importlib.reload(faro.servidor)
