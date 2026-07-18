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


def _env_con_fixture_dedupe() -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(FIXTURES_DEDUPE) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def test_deduplica_clases_reexportadas_por_identidad():
    """Muchas librerías re-exportan una clase en el paquete raíz y en su submódulo
    real (p. ej. sqlalchemy.Connection es sqlalchemy.engine.Connection). Sin
    deduplicar, ambas rutas aparecen como símbolos "distintos" y cualquier consulta
    sin calificar (p. ej. "Connection.execute") sale ambigua por error, aunque hay
    un solo símbolo real. `paquete_prueba` (fixture local) reproduce ese patrón:
    `paquete_prueba.Cosa` es literalmente `paquete_prueba.base.Cosa`.
    """
    r = _correr(
        {"libreria": "paquete_prueba", "modulos": ["paquete_prueba", "paquete_prueba.base"]},
        env=_env_con_fixture_dedupe(),
    )
    coincidencias = [s["nombre"] for s in r["simbolos"] if s["nombre"].endswith(".Cosa.metodo")]

    assert coincidencias == ["paquete_prueba.base.Cosa.metodo"]


def test_metodo_heredado_sin_override_resuelve_bajo_el_nombre_de_la_hija():
    """CursorResult.fetchall existe en SQLAlchemy real pero vive en la clase base
    Result, sin sobreescribir. Antes de este fix, el extractor solo miraba
    vars(clase) propia y devolvía NoEncontrado pese a que el método existe.
    `Hija` (fixture local) hereda `metodo_base` de `Base` sin tocarlo: debe resolver
    bajo el nombre de Hija, con la doc de Base."""
    r = _correr(
        {"libreria": "paquete_prueba", "modulos": ["paquete_prueba.base"]},
        env=_env_con_fixture_dedupe(),
    )
    por_nombre = {s["nombre"]: s["doc"] for s in r["simbolos"]}

    assert "paquete_prueba.base.Hija.metodo_base" in por_nombre
    assert "Doc original de Base" in por_nombre["paquete_prueba.base.Hija.metodo_base"]


def test_metodo_heredado_con_override_no_pisa_la_doc_propia():
    """HijaConOverride sobreescribe metodo_base: debe ganar SU docstring, no el de
    la clase base — igual que Python resuelve el método en runtime."""
    r = _correr(
        {"libreria": "paquete_prueba", "modulos": ["paquete_prueba.base"]},
        env=_env_con_fixture_dedupe(),
    )
    por_nombre = {s["nombre"]: s["doc"] for s in r["simbolos"]}

    assert "Doc propia de HijaConOverride" in por_nombre["paquete_prueba.base.HijaConOverride.metodo_base"]


def test_la_firma_de_una_funcion_se_extrae():
    r = _correr({"libreria": "textwrap", "modulos": ["textwrap"]})
    por_nombre = {s["nombre"]: s["firma"] for s in r["simbolos"]}
    assert por_nombre["textwrap.dedent"] == "(text)"


def test_classmethod_no_tiene_cls_en_la_firma():
    """pathlib.Path.cwd no recibe argumentos del llamador (cls lo pone Python solo)."""
    r = _correr({"libreria": "pathlib", "modulos": ["pathlib"]})
    por_nombre = {s["nombre"]: s["firma"] for s in r["simbolos"]}
    assert por_nombre["pathlib.Path.cwd"] == "()"


def test_metodo_de_instancia_no_tiene_self_en_la_firma():
    r = _correr({"libreria": "textwrap", "modulos": ["textwrap"]})
    por_nombre = {s["nombre"]: s["firma"] for s in r["simbolos"]}
    firma = por_nombre["textwrap.TextWrapper.wrap"]
    assert firma is not None
    assert "self" not in firma
    assert "text" in firma


def test_property_no_rompe_la_extraccion_y_no_tiene_firma():
    """pathlib.Path.parent es una property heredada de PurePath: no es invocable,
    inspect.signature() falla — debe dar firma=None sin tumbar la extracción."""
    r = _correr({"libreria": "pathlib", "modulos": ["pathlib"]})
    por_nombre = {s["nombre"]: s for s in r["simbolos"]}
    assert "pathlib.Path.parent" in por_nombre
    assert por_nombre["pathlib.Path.parent"]["firma"] is None
    assert "logical parent" in por_nombre["pathlib.Path.parent"]["doc"].lower()


def test_modulos_null_descubre_submodulos_automaticamente():
    """Sin lista fija de módulos (modulos=None), el extractor camina los
    submódulos públicos solo. json (stdlib) tiene submódulos reales:
    json.decoder, json.encoder, json.scanner."""
    r = _correr({"libreria": "json", "modulos": None})
    nombres = {s["nombre"] for s in r["simbolos"]}
    assert any(n.startswith("json.decoder.") or n == "json.decoder" for n in nombres)


def test_descubrimiento_automatico_excluye_submodulos_privados():
    r = _correr(
        {"libreria": "paquete_prueba", "modulos": None},
        env=_env_con_fixture_dedupe(),
    )
    nombres = {s["nombre"] for s in r["simbolos"]}
    assert not any("_interno" in n for n in nombres)
    # pero sí encuentra lo público, sin que nadie le diga "paquete_prueba.base":
    assert any(n.startswith("paquete_prueba.base.") for n in nombres)


def test_descubrimiento_automatico_no_rompe_con_modulo_simple():
    """textwrap no es un paquete (no tiene __path__): cae de vuelta a [libreria]."""
    r = _correr({"libreria": "textwrap", "modulos": None})
    nombres = {s["nombre"] for s in r["simbolos"]}
    assert "textwrap.dedent" in nombres
