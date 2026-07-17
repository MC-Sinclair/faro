from faro.parseo import extraer_deprecacion

# Docstring real de sqlalchemy.orm.Query.get en 2.0.36 (verificado contra el paquete).
DOC_QUERY_GET = """Return an instance based on the given primary key identifier,
or ``None`` if not found.

.. deprecated:: 2.0 The :meth:`_orm.Query.get` method is considered legacy as of the 1.x series of SQLAlchemy and becomes a legacy construct in 2.0. The method is now available as :meth:`_orm.Session.get` (Background on SQLAlchemy 2.0 at: :ref:`migration_20_toplevel`)

E.g.::

    my_user = session.query(User).get(5)
"""

DOC_SIN_DEPRECACION = """Execute a SQL expression construct.

Returns a :class:`_engine.Result` object.
"""


def test_detecta_la_deprecacion_y_su_version():
    d = extraer_deprecacion(DOC_QUERY_GET)
    assert d is not None
    assert d.desde == "2.0"


def test_extrae_el_reemplazo_sugerido_por_la_libreria():
    """El caso que da sentido al proyecto: te dice qué usar en su lugar."""
    d = extraer_deprecacion(DOC_QUERY_GET)
    assert d is not None
    assert d.reemplazo == "Session.get"


def test_conserva_el_mensaje_completo():
    d = extraer_deprecacion(DOC_QUERY_GET)
    assert d is not None
    assert "legacy" in d.mensaje


def test_un_docstring_sano_no_inventa_deprecacion():
    assert extraer_deprecacion(DOC_SIN_DEPRECACION) is None


def test_docstring_vacio_no_revienta():
    assert extraer_deprecacion("") is None


def test_deprecacion_sin_reemplazo_identificable():
    doc = ".. deprecated:: 1.4 Esto ya no se usa y no hay alternativa directa."
    d = extraer_deprecacion(doc)
    assert d is not None
    assert d.desde == "1.4"
    assert d.reemplazo is None
