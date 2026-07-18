"""Tests de contrato: tocan SQLAlchemy de verdad, en el intérprete de los tests.

Corren con:  uv run pytest -m contrato
No corren en el ciclo rápido de TDD.

Verifican que la REALIDAD sigue siendo como creemos. Si SQLAlchemy cambia el
formato de sus docstrings, estos tests se caen y los fakes no se enteran.
"""

import sys

import pytest

from faro.dominio import Ambiguo, Fragmento, NoEncontrado
from faro.fuentes.local import FuenteLocal
from faro.resolver import ResolverDeDocs

pytestmark = pytest.mark.contrato


@pytest.fixture(scope="module")
def resolver() -> ResolverDeDocs:
    return ResolverDeDocs(FuenteLocal(python=sys.executable))


def test_la_version_instalada_es_la_exacta(resolver):
    """No '2.0': la exacta."""
    assert resolver.listar_versiones("sqlalchemy") == ["2.0.36"]


def test_session_execute_existe_y_trae_su_doc(resolver):
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Session.execute")
    assert isinstance(r, Fragmento)
    assert r.simbolo == "sqlalchemy.orm.Session.execute"
    assert "Execute a SQL expression construct" in r.texto


def test_query_get_existe_en_2_0_y_esta_deprecado(resolver):
    """EL test. El asistente afirmó de memoria que Query.get no existía en 2.0.
    Existe, y está marcado como legacy. Esto es lo que Faro previene."""
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Query.get")

    assert isinstance(r, Fragmento), "Query.get SÍ existe en 2.0"
    assert r.deprecacion is not None, "y está deprecado"
    assert r.deprecacion.desde == "2.0"
    assert r.deprecacion.reemplazo == "Session.get"


def test_pedir_la_1_4_teniendo_la_2_0_no_devuelve_nada(resolver):
    """Regla 3 contra la realidad."""
    r = resolver.buscar_doc("sqlalchemy", "1.4", "Session.execute")
    assert isinstance(r, NoEncontrado)
    assert "2.0.36" in r.motivo


def test_connection_execute_no_es_ambiguo_pese_al_reexport(resolver):
    """sqlalchemy.Connection ES sqlalchemy.engine.Connection (mismo objeto,
    re-exportado). Sin deduplicar por identidad en el extractor, esta consulta
    salía Ambiguo por error — el mismo símbolo contado dos veces, no dos símbolos
    reales. Encontrado usando Faro contra sí mismo (dogfooding)."""
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Connection.execute")
    assert isinstance(r, Fragmento), "es un solo símbolo real, no debería ser ambiguo"
    assert r.simbolo == "sqlalchemy.engine.Connection.execute"


def test_metodos_heredados_resuelven_p_ej_cursorresult_fetchall(resolver):
    """fetchall y scalar viven en Result, no en CursorResult (que hereda sin
    sobreescribir). Antes del fix de herencia, el extractor solo miraba
    vars(clase) propia y esto daba NoEncontrado pese a existir de verdad.
    Encontrado usando Faro contra sí mismo (dogfooding)."""
    for consulta in ["CursorResult.fetchall", "CursorResult.scalar"]:
        r = resolver.buscar_doc("sqlalchemy", "2.0.36", consulta)
        assert isinstance(r, Fragmento), f"{consulta} existe de verdad (heredado de Result)"
        assert r.simbolo == f"sqlalchemy.engine.{consulta}"


def test_la_firma_real_de_session_execute_incluye_statement(resolver):
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Session.execute")
    assert isinstance(r, Fragmento)
    assert r.firma is not None
    assert "statement" in r.firma
    assert "self" not in r.firma


def test_un_ambiguo_real_no_esconde_los_candidatos_deprecados(resolver):
    """'get' resuelve a 8 símbolos en SQLAlchemy 2.0.36, y 2 son legacy
    (Query.get, AppenderQuery.get). Antes, Faro listaba los 8 como iguales y
    en verificar_simbolos decía solo "existe" — falsamente tranquilizador.
    Este es el caso fundacional del proyecto llegando por la vía ambigua."""
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "get")
    assert isinstance(r, Ambiguo)

    deprecados = {d.nombre: d.deprecacion for d in r.deprecados}
    assert "sqlalchemy.orm.Query.get" in deprecados
    assert deprecados["sqlalchemy.orm.Query.get"].reemplazo == "Session.get"
    assert "sqlalchemy.orm.Session.get" not in deprecados  # el vigente no se marca


def test_un_simbolo_real_sin_docstring_no_se_reporta_inexistente(resolver):
    """Connection.commit_prepared existe en 2.0.36 y no declara docstring. El
    extractor lo descartaba entero, así que Faro decía "NO EXISTE" sobre API real."""
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Connection.commit_prepared")
    assert isinstance(r, Fragmento), "existe de verdad: no tener doc no es no existir"
    assert r.texto is None
    assert r.firma is not None


def test_faro_se_encuentra_a_si_mismo(resolver):
    """Dogfooding convertido en regresión permanente: Faro está instalado en su
    propio venv y declaraba inexistentes 2 de sus 3 herramientas MCP, porque sus
    métodos no llevan docstring. Si vuelve a negarse a sí mismo, esto se cae."""
    version = resolver.listar_versiones("faro")
    assert not isinstance(version, NoEncontrado), "Faro debería verse instalado"

    for herramienta in ["ResolverDeDocs.buscar_doc", "ResolverDeDocs.listar_versiones"]:
        r = resolver.buscar_doc("faro", version[0], herramienta)
        assert isinstance(r, Fragmento), f"{herramienta} existe: es una herramienta de Faro"


def test_verificar_simbolos_contra_sqlalchemy_real(resolver):
    r = resolver.verificar_simbolos(
        "sqlalchemy", "2.0.36", ["Session.get", "Query.get", "Session.metodo_inventado"]
    )
    por_nombre = {v.simbolo: v for v in r}

    assert por_nombre["Session.get"].existe
    assert por_nombre["Session.get"].deprecacion is None

    assert por_nombre["Query.get"].existe
    assert por_nombre["Query.get"].deprecacion is not None

    assert not por_nombre["Session.metodo_inventado"].existe
