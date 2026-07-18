import json
import subprocess
import sys
from pathlib import Path

EXTRACTOR = Path(__file__).parent.parent / "src" / "faro" / "fuentes" / "extractor.py"


def _correr(peticion: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(EXTRACTOR), json.dumps(peticion)],
        capture_output=True,
        text=True,
        timeout=60,
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
