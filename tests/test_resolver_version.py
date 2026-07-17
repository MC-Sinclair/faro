import pytest

from faro.dominio import NoEncontrado
from faro.fuentes.fake import FuenteFake, simbolos_de_prueba
from faro.resolver import ResolverDeDocs, version_compatible


@pytest.fixture
def resolver() -> ResolverDeDocs:
    return ResolverDeDocs(FuenteFake(version="2.0.36", entradas=simbolos_de_prueba()))


def test_listar_versiones_devuelve_la_instalada():
    r = ResolverDeDocs(FuenteFake(version="2.0.36", entradas=[]))
    assert r.listar_versiones("sqlalchemy") == ["2.0.36"]


def test_listar_versiones_de_libreria_desconocida_falla_honestamente(resolver):
    res = resolver.listar_versiones("django")
    assert isinstance(res, NoEncontrado)
    assert "sqlalchemy" in res.motivo  # dice cuáles SÍ conoce


def test_listar_versiones_de_libreria_no_instalada_no_devuelve_lista_vacia():
    """Regla 3: una lista vacía es una respuesta ambigua. Preferimos NoEncontrado."""
    r = ResolverDeDocs(FuenteFake(version=None, entradas=[]))
    res = r.listar_versiones("sqlalchemy")
    assert isinstance(res, NoEncontrado)


def test_una_version_exacta_es_compatible_consigo_misma():
    assert version_compatible("2.0.36", "2.0.36")


def test_un_prefijo_de_version_es_compatible():
    assert version_compatible("2.0", "2.0.36")
    assert version_compatible("2", "2.0.36")


def test_una_version_distinta_no_es_compatible():
    """El corazón del asunto: pedir 1.4 teniendo 2.0.36 no cuela."""
    assert not version_compatible("1.4", "2.0.36")


def test_el_prefijo_debe_ser_de_componente_completo():
    """'2.0' no debe tragarse '2.01'. La comparación es por componentes, no por texto."""
    assert not version_compatible("2.0", "2.01.0")
