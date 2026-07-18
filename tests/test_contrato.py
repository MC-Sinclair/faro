"""Tests de contrato: tocan SQLAlchemy de verdad, en el intérprete de los tests.

Corren con:  uv run pytest -m contrato
No corren en el ciclo rápido de TDD.

Verifican que la REALIDAD sigue siendo como creemos. Si SQLAlchemy cambia el
formato de sus docstrings, estos tests se caen y los fakes no se enteran.
"""

import sys

import pytest

from faro.dominio import Fragmento, NoEncontrado
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
