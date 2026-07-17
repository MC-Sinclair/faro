import pytest
from dataclasses import FrozenInstanceError

from faro.dominio import Deprecacion, Fragmento, Ambiguo, NoEncontrado


def test_un_fragmento_no_se_puede_construir_sin_procedencia():
    """Regla 2: la cita es estructural. Sin librería, versión y símbolo no hay Fragmento."""
    with pytest.raises(TypeError):
        Fragmento(texto="algo")  # type: ignore[call-arg]


def test_un_fragmento_lleva_su_procedencia_dentro():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session.execute",
        texto="Execute a SQL expression construct.",
        deprecacion=None,
    )
    assert f.libreria == "sqlalchemy"
    assert f.version == "2.0.36"
    assert f.simbolo == "sqlalchemy.orm.Session.execute"


def test_un_fragmento_es_inmutable():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="x.y",
        texto="doc",
        deprecacion=None,
    )
    with pytest.raises(FrozenInstanceError):
        f.version = "1.4"  # type: ignore[misc]


def test_no_encontrado_siempre_explica_el_motivo():
    """Regla 3: el 'no lo tengo' nunca es mudo."""
    with pytest.raises(TypeError):
        NoEncontrado()  # type: ignore[call-arg]
    assert NoEncontrado(motivo="no está instalada").motivo


def test_ambiguo_lista_los_candidatos_y_no_elige():
    a = Ambiguo(consulta="select", candidatos=["a.select", "b.select"])
    assert len(a.candidatos) == 2
