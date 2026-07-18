import pytest

from faro.dominio import Ambiguo, Fragmento, NoEncontrado
from faro.fuentes.fake import FuenteFake, simbolos_de_prueba
from faro.resolver import ResolverDeDocs


@pytest.fixture
def resolver() -> ResolverDeDocs:
    return ResolverDeDocs(FuenteFake(version="2.0.36", entradas=simbolos_de_prueba()))


def test_resuelve_por_nombre_completo(resolver):
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "sqlalchemy.orm.Session.execute")
    assert isinstance(r, Fragmento)
    assert r.simbolo == "sqlalchemy.orm.Session.execute"
    assert r.version == "2.0.36"


def test_resuelve_por_sufijo(resolver):
    """Nadie tipea el namespace completo."""
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Session.execute")
    assert isinstance(r, Fragmento)
    assert r.simbolo == "sqlalchemy.orm.Session.execute"


def test_el_fragmento_arrastra_la_firma(resolver):
    """Cableado completo extractor→dominio→resolver: la firma de la entrada del
    fixture llega intacta hasta el Fragmento."""
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Session.execute")
    assert isinstance(r, Fragmento)
    assert r.firma == "(statement, params=None, *, execution_options={})"


def test_el_fragmento_arrastra_la_deprecacion(resolver):
    """EL caso. Query.get existe en 2.0 pero está obsoleto: hay que decirlo."""
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Query.get")
    assert isinstance(r, Fragmento)
    assert r.deprecacion is not None
    assert r.deprecacion.desde == "2.0"
    assert r.deprecacion.reemplazo == "Session.get"


def test_consulta_ambigua_lista_candidatos_y_no_elige(resolver):
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "select")
    assert isinstance(r, Ambiguo)
    assert len(r.candidatos) == 2
    assert "sqlalchemy.schema.Table.select" in r.candidatos


def test_el_ambiguo_marca_cuales_candidatos_estan_deprecados(resolver):
    """Listar 'Query.get' y 'Session.get' como opciones equivalentes esconde que
    una es legacy. Faro tiene el dato: hay que mostrarlo."""
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "get")
    assert isinstance(r, Ambiguo)
    assert "sqlalchemy.orm.Session.get" in r.candidatos  # la lista no cambia

    nombres = [d.nombre for d in r.deprecados]
    assert nombres == ["sqlalchemy.orm.Query.get"]
    assert r.deprecados[0].deprecacion.reemplazo == "Session.get"


def test_el_ambiguo_sin_deprecados_no_inventa_ninguno(resolver):
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "select")
    assert isinstance(r, Ambiguo)
    assert r.deprecados == []


def test_simbolo_inexistente_falla_honestamente(resolver):
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Session.no_existe")
    assert isinstance(r, NoEncontrado)


def test_pedir_otra_version_nunca_devuelve_la_instalada(resolver):
    """Regla 3, el test más importante del proyecto."""
    r = resolver.buscar_doc("sqlalchemy", "1.4", "Session.execute")
    assert isinstance(r, NoEncontrado)
    assert "2.0.36" in r.motivo  # dice cuál SÍ hay
    assert not isinstance(r, Fragmento)


def test_libreria_desconocida_falla_honestamente(resolver):
    r = resolver.buscar_doc("django", "5.0", "Model.save")
    assert isinstance(r, NoEncontrado)
