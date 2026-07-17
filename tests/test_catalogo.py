from faro.catalogo import CATALOGO, EntradaCatalogo


def test_el_catalogo_conoce_sqlalchemy():
    assert "sqlalchemy" in CATALOGO


def test_el_catalogo_es_data_no_codigo():
    """Agregar una librería debe ser agregar una entrada, sin tocar el núcleo."""
    e = CATALOGO["sqlalchemy"]
    assert isinstance(e, EntradaCatalogo)
    assert "sqlalchemy.orm" in e.modulos
    assert len(e.modulos) >= 5
