import pytest

from faro.dominio import EntradaSimbolo, NoEncontrado
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


def test_un_ambiguo_no_esconde_que_algunos_candidatos_estan_deprecados(resolver):
    """'get' coincide con Session.get (vigente) y Query.get (deprecado). Decir
    solo "existe" es falsamente tranquilizador: hay una trampa entre las
    opciones y Faro tiene el dato."""
    r = resolver.verificar_simbolos("sqlalchemy", "2.0.36", ["get"])
    v = r[0]
    assert v.existe
    assert v.resuelto_como is None  # sigue sin elegir por el usuario

    nombres = [d.nombre for d in v.deprecados]
    assert nombres == ["sqlalchemy.orm.Query.get"]
    assert v.deprecados[0].deprecacion.reemplazo == "Session.get"


def test_un_ambiguo_sin_deprecados_no_inventa_ninguno(resolver):
    """'select' coincide con dos símbolos, ninguno deprecado."""
    r = resolver.verificar_simbolos("sqlalchemy", "2.0.36", ["select"])
    assert r[0].deprecados == []


def test_verificar_arrastra_el_origen_propio(resolver):
    r = resolver.verificar_simbolos("sqlalchemy", "2.0.36", ["Session.execute"])
    assert r[0].modulo_origen == "sqlalchemy"


def test_verificar_ambiguo_no_afirma_un_origen_unico(resolver):
    r = resolver.verificar_simbolos("sqlalchemy", "2.0.36", ["select"])
    assert r[0].modulo_origen is None


def test_verificar_marca_un_simbolo_ajeno():
    """Reproduce el defecto medido: Path.cwd existe pero no es de faro."""
    entradas = [
        EntradaSimbolo(
            nombre="faro.fuentes.local.Path.cwd",
            doc="doc",
            deprecacion=None,
            modulo_origen="pathlib",
            firma="()",
        )
    ]
    resolver_faro = ResolverDeDocs(FuenteFake(version="0.1.0", entradas=entradas, libreria="faro"))
    v = resolver_faro.verificar_simbolos("faro", "0.1.0", ["Path.cwd"])
    assert v[0].existe
    assert v[0].modulo_origen == "pathlib"
