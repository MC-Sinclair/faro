from faro.dominio import Ambiguo, Deprecacion, Fragmento, NoEncontrado, Verificacion
from faro.presentacion import TOPE_CARACTERES, formatear, formatear_verificaciones, limpiar_rst


def test_la_cita_siempre_aparece():
    """Regla 2: librería, versión y símbolo, siempre."""
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session.execute",
        texto="Execute a SQL expression construct.",
        deprecacion=None,
    )
    salida = formatear(f)
    assert "sqlalchemy 2.0.36" in salida
    assert "sqlalchemy.orm.Session.execute" in salida


def test_la_deprecacion_se_grita_no_se_susurra():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Query.get",
        texto="Return an instance...",
        deprecacion=Deprecacion(desde="2.0", mensaje="legacy", reemplazo="Session.get"),
    )
    salida = formatear(f)
    assert "DEPRECADO" in salida
    assert "Session.get" in salida


def test_limpia_el_markup_rst():
    assert limpiar_rst("Returns a :class:`_engine.Result` object.") == (
        "Returns a Result object."
    )


def test_recorta_los_docstrings_gigantes():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session",
        texto="x" * 20_000,
        deprecacion=None,
    )
    salida = formatear(f)
    assert len(salida) < TOPE_CARACTERES + 500
    assert "recortado" in salida


def test_el_no_encontrado_explica_el_motivo():
    salida = formatear(NoEncontrado(motivo="Pediste 1.4, pero el entorno tiene 2.0.36."))
    assert "2.0.36" in salida


def test_el_ambiguo_lista_candidatos():
    salida = formatear(Ambiguo(consulta="select", candidatos=["a.select", "b.select"]))
    assert "a.select" in salida
    assert "b.select" in salida


def test_las_verificaciones_marcan_lo_que_no_existe():
    vs = [
        Verificacion(simbolo="Session.execute", existe=True, resuelto_como="x.Session.execute", deprecacion=None),
        Verificacion(simbolo="Session.inventado", existe=False, resuelto_como=None, deprecacion=None),
    ]
    salida = formatear_verificaciones(vs)
    assert "NO EXISTE" in salida
