import pytest

from faro.dominio import NoEncontrado
from faro.fuentes.fake import FuenteFake, simbolos_de_prueba
from faro.resolver import ResolverDeDocs


@pytest.fixture
def resolver() -> ResolverDeDocs:
    return ResolverDeDocs(FuenteFake(version="2.0.36", entradas=simbolos_de_prueba()))


def test_verifica_una_lista_de_simbolos_afirmados(resolver):
    r = resolver.verificar_simbolos(
        "sqlalchemy", "2.0.36", ["Session.execute", "Query.get", "Session.inventado"]
    )
    assert not isinstance(r, NoEncontrado)
    por_nombre = {v.simbolo: v for v in r}

    assert por_nombre["Session.execute"].existe
    assert por_nombre["Session.execute"].deprecacion is None

    assert por_nombre["Query.get"].existe
    assert por_nombre["Query.get"].deprecacion is not None
    assert por_nombre["Query.get"].deprecacion.reemplazo == "Session.get"

    assert not por_nombre["Session.inventado"].existe
    assert por_nombre["Session.inventado"].resuelto_como is None


def test_verificar_dice_a_que_simbolo_completo_resolvio(resolver):
    r = resolver.verificar_simbolos("sqlalchemy", "2.0.36", ["Session.execute"])
    assert r[0].resuelto_como == "sqlalchemy.orm.Session.execute"


def test_un_simbolo_ambiguo_no_se_da_por_existente_a_ciegas(resolver):
    r = resolver.verificar_simbolos("sqlalchemy", "2.0.36", ["select"])
    assert r[0].existe
    assert r[0].resuelto_como is None  # ambiguo: no afirmamos a cuál


def test_verificar_respeta_la_guarda_de_version(resolver):
    r = resolver.verificar_simbolos("sqlalchemy", "1.4", ["Session.execute"])
    assert isinstance(r, NoEncontrado)
