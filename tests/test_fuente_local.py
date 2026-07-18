import sys

import pytest

from faro.fuentes.local import FuenteLocal


@pytest.fixture
def fuente() -> FuenteLocal:
    """Apuntamos al intérprete de los propios tests: siempre tiene la stdlib."""
    return FuenteLocal(python=sys.executable)


def test_lee_los_simbolos_de_un_venv_real(fuente):
    simbolos = fuente.simbolos("textwrap")
    nombres = {e.nombre for e in simbolos}
    assert "textwrap.dedent" in nombres


def test_parsea_la_deprecacion_del_lado_de_faro(fuente, monkeypatch):
    """El extractor vuelca docs crudos; FuenteLocal los pasa por parseo.py."""
    simbolos = fuente.simbolos("textwrap")
    # textwrap no tiene deprecaciones: todas deben ser None, sin reventar.
    assert all(e.deprecacion is None for e in simbolos)


def test_libreria_no_instalada_devuelve_none(fuente):
    assert fuente.version_instalada("paquete_que_no_existe_xyz") is None


def test_un_interprete_invalido_falla_explicitamente():
    """Regla 3: nunca un fallback silencioso al venv de Faro."""
    f = FuenteLocal(python="/ruta/que/no/existe/python")
    with pytest.raises(RuntimeError, match="intérprete"):
        f.version_instalada("textwrap")
