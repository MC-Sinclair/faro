import json
import os
import subprocess
import sys
from pathlib import Path

EXTRACTOR = Path(__file__).parent.parent / "src" / "faro" / "fuentes" / "extractor.py"
FIXTURES_DEDUPE = Path(__file__).parent / "fixtures_extractor_dedupe"


def _correr(peticion: dict, env: dict | None = None) -> dict:
    proc = subprocess.run(
        [sys.executable, str(EXTRACTOR), json.dumps(peticion)],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_extrae_simbolos_de_un_modulo_de_la_stdlib():
    """Usamos textwrap: siempre está, no necesita instalar nada."""
    r = _correr({"libreria": "textwrap", "modulos": ["textwrap"]})
    nombres = {s["nombre"] for s in r["simbolos"]}
    assert "textwrap.dedent" in nombres


def test_los_simbolos_traen_su_docstring():
    r = _correr({"libreria": "textwrap", "modulos": ["textwrap"]})
    dedent = next(s for s in r["simbolos"] if s["nombre"] == "textwrap.dedent")
    assert "indent" in dedent["doc"].lower()


def test_recorre_los_metodos_de_las_clases():
    r = _correr({"libreria": "textwrap", "modulos": ["textwrap"]})
    nombres = {s["nombre"] for s in r["simbolos"]}
    assert "textwrap.TextWrapper.wrap" in nombres


def test_una_libreria_no_instalada_da_version_nula_y_no_revienta():
    r = _correr({"libreria": "no_existe_este_paquete_xyz", "modulos": ["no_existe_xyz"]})
    assert r["version"] is None
    assert r["simbolos"] == []


def test_no_falla_si_un_modulo_del_catalogo_no_se_puede_importar():
    """Robustez: un módulo roto no debe tumbar la extracción de los demás."""
    r = _correr({"libreria": "textwrap", "modulos": ["textwrap", "modulo.que.no.existe"]})
    nombres = {s["nombre"] for s in r["simbolos"]}
    assert "textwrap.dedent" in nombres


def test_extrae_classmethods_de_las_clases():
    """pathlib.Path.cwd es un classmethod real de la stdlib: siempre disponible.

    Regresión: el extractor solo capturaba inspect.isfunction/property en
    vars(clase), lo que omite descriptores classmethod/staticmethod (viven
    como objetos classmethod/staticmethod en el __dict__ de la clase, no como
    funciones planas) — causaba falsos "no existe" en símbolos reales como
    sqlalchemy.engine.URL.create.
    """
    r = _correr({"libreria": "pathlib", "modulos": ["pathlib"]})
    nombres = {s["nombre"] for s in r["simbolos"]}
    assert "pathlib.Path.cwd" in nombres


def test_deduplica_clases_reexportadas_por_identidad():
    """Muchas librerías re-exportan una clase en el paquete raíz y en su submódulo
    real (p. ej. sqlalchemy.Connection es sqlalchemy.engine.Connection). Sin
    deduplicar, ambas rutas aparecen como símbolos "distintos" y cualquier consulta
    sin calificar (p. ej. "Connection.execute") sale ambigua por error, aunque hay
    un solo símbolo real. `paquete_prueba` (fixture local) reproduce ese patrón:
    `paquete_prueba.Cosa` es literalmente `paquete_prueba.base.Cosa`.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(FIXTURES_DEDUPE) + os.pathsep + env.get("PYTHONPATH", "")

    r = _correr(
        {"libreria": "paquete_prueba", "modulos": ["paquete_prueba", "paquete_prueba.base"]},
        env=env,
    )
    coincidencias = [s["nombre"] for s in r["simbolos"] if s["nombre"].endswith(".Cosa.metodo")]

    assert coincidencias == ["paquete_prueba.base.Cosa.metodo"]
