import os
import subprocess
import sys
from pathlib import Path

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


def test_descubre_submodulos_de_una_libreria_sin_catalogar(fuente):
    """email no tiene entrada curada en catalogo.py. MIMEText vive en
    email.mime.text — NO está re-exportada en el email top-level (verificado:
    "MIMEText" not in dir(email)) — así que encontrarla prueba que el
    descubrimiento automático caminó de verdad el submódulo, no que escaneó
    solo el paquete raíz."""
    simbolos = fuente.simbolos("email")
    nombres = {e.nombre for e in simbolos}
    assert "email.mime.text.MIMEText" in nombres


def test_libreria_no_instalada_devuelve_none(fuente):
    assert fuente.version_instalada("paquete_que_no_existe_xyz") is None


def test_un_interprete_invalido_falla_explicitamente():
    """Regla 3: nunca un fallback silencioso al venv de Faro."""
    f = FuenteLocal(python="/ruta/que/no/existe/python")
    with pytest.raises(RuntimeError, match="intérprete"):
        f.version_instalada("textwrap")


def test_salida_no_json_del_extractor_falla_explicitamente(fuente, monkeypatch):
    """Si el intérprete objetivo ensucia stdout, no debe reventar con un
    json.JSONDecodeError crudo — debe envolverse en el mismo RuntimeError que
    usan los demás fallos de este borde (proceso, timeout, retorno != 0)."""

    def _run_falso(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="esto no es json", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _run_falso)
    with pytest.raises(RuntimeError, match="no-JSON"):
        fuente.version_instalada("textwrap")


def test_modulo_origen_distingue_lo_propio_de_lo_ajeno(monkeypatch):
    """Cableado completo extractor→FuenteLocal: BaseAjena vive en otro_paquete
    pero se importa en paquete_prueba.base — su origen real debe llegar intacto
    hasta EntradaSimbolo, distinto del origen de un símbolo genuinamente propio."""
    fixtures = Path(__file__).parent / "fixtures_extractor_dedupe"
    monkeypatch.setenv(
        "PYTHONPATH", str(fixtures) + os.pathsep + os.environ.get("PYTHONPATH", "")
    )
    fuente = FuenteLocal(python=sys.executable)
    por_nombre = {e.nombre: e for e in fuente.simbolos("paquete_prueba")}

    assert por_nombre["paquete_prueba.base.Cosa.metodo"].modulo_origen == "paquete_prueba"
    assert por_nombre["paquete_prueba.base.BaseAjena"].modulo_origen == "otro_paquete"
