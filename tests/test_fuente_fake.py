from faro.fuentes.fake import FuenteFake, simbolos_de_prueba


def test_la_fake_reporta_la_version_que_le_dieron():
    f = FuenteFake(version="2.0.36", entradas=simbolos_de_prueba())
    assert f.version_instalada("sqlalchemy") == "2.0.36"


def test_la_fake_reporta_none_si_la_libreria_no_esta():
    f = FuenteFake(version=None, entradas=[])
    assert f.version_instalada("sqlalchemy") is None


def test_la_fake_discrimina_por_libreria():
    """Sin el gate de catálogo en resolver.py, la fake tiene que distinguir sola
    la librería que representa de cualquier otra — antes lo hacía el gate."""
    f = FuenteFake(version="2.0.36", entradas=simbolos_de_prueba())
    assert f.version_instalada("django") is None
    assert f.simbolos("django") == []


def test_los_simbolos_de_prueba_incluyen_el_caso_query_get():
    """Query.get existe en 2.0 Y está deprecado. Es el caso que funda el proyecto."""
    nombres = {e.nombre for e in simbolos_de_prueba()}
    assert "sqlalchemy.orm.Query.get" in nombres

    query_get = next(e for e in simbolos_de_prueba() if e.nombre == "sqlalchemy.orm.Query.get")
    assert query_get.deprecacion is not None
    assert query_get.deprecacion.reemplazo == "Session.get"


def test_los_simbolos_de_prueba_son_propios_de_sqlalchemy():
    """Son símbolos reales de SQLAlchemy: su origen declarado debe ser la propia
    librería, no otra."""
    assert all(e.modulo_origen == "sqlalchemy" for e in simbolos_de_prueba())
