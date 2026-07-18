from faro.dominio import (
    Ambiguo,
    CandidatoDeprecado,
    Deprecacion,
    Fragmento,
    NoEncontrado,
    Verificacion,
)
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


def test_la_firma_aparece_si_esta_presente():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session.execute",
        texto="Execute a SQL expression construct.",
        deprecacion=None,
        firma="(statement, parameters=None)",
    )
    salida = formatear(f)
    assert "(statement, parameters=None)" in salida


def test_sin_firma_no_agrega_ninguna_linea_de_mas():
    """firma=None (el caso por default) no debe cambiar la forma del output."""
    con_datos_comunes = dict(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session.execute",
        texto="Execute a SQL expression construct.",
        deprecacion=None,
    )
    sin_firma = formatear(Fragmento(**con_datos_comunes, firma=None))
    explicito_none = formatear(Fragmento(**con_datos_comunes))
    assert sin_firma == explicito_none


def test_la_firma_aparece_en_las_verificaciones():
    vs = [
        Verificacion(
            simbolo="Session.execute",
            existe=True,
            resuelto_como="sqlalchemy.orm.Session.execute",
            deprecacion=None,
            firma="(statement, parameters=None)",
        ),
    ]
    salida = formatear_verificaciones(vs)
    assert "(statement, parameters=None)" in salida


def test_verificacion_sin_firma_no_agrega_nada_de_mas():
    con_firma_none = Verificacion(
        simbolo="Session.execute", existe=True, resuelto_como="x.Session.execute", deprecacion=None
    )
    assert formatear_verificaciones([con_firma_none]) == "Session.execute: existe (x.Session.execute)"


def test_un_simbolo_sin_documentacion_lo_dice_y_conserva_cita_y_firma():
    f = Fragmento(
        libreria="faro",
        version="0.1.0",
        simbolo="faro.resolver.ResolverDeDocs.buscar_doc",
        texto=None,
        deprecacion=None,
        firma="(libreria: str, version: str, consulta: str)",
    )
    salida = formatear(f)

    assert "faro 0.1.0" in salida  # la cita no se pierde (regla 2)
    assert "(libreria: str, version: str, consulta: str)" in salida
    assert "no declara documentación" in salida


def test_con_texto_la_salida_no_cambia():
    """Regresión: el aviso solo aparece cuando texto es None."""
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session.execute",
        texto="Execute a SQL expression construct.",
        deprecacion=None,
    )
    assert "no declara documentación" not in formatear(f)


def _query_get_deprecado() -> CandidatoDeprecado:
    return CandidatoDeprecado(
        nombre="sqlalchemy.orm.Query.get",
        deprecacion=Deprecacion(desde="2.0", mensaje="legacy", reemplazo="Session.get"),
    )


def test_el_ambiguo_marca_en_linea_los_candidatos_deprecados():
    salida = formatear(
        Ambiguo(
            consulta="get",
            candidatos=["sqlalchemy.orm.Query.get", "sqlalchemy.orm.Session.get"],
            deprecados=[_query_get_deprecado()],
        )
    )
    linea_query = next(l for l in salida.splitlines() if "Query.get" in l)
    linea_session = next(l for l in salida.splitlines() if "Session.get" in l and "Query" not in l)

    assert "DEPRECADO" in linea_query
    assert "Session.get" in linea_query  # el reemplazo
    assert "DEPRECADO" not in linea_session  # el vigente no se marca


def test_el_ambiguo_sin_deprecados_se_ve_igual_que_siempre():
    comunes = dict(consulta="select", candidatos=["a.select", "b.select"])
    assert formatear(Ambiguo(**comunes, deprecados=[])) == formatear(Ambiguo(**comunes))


def test_la_verificacion_ambigua_nombra_los_deprecados():
    salida = formatear_verificaciones(
        [
            Verificacion(
                simbolo="get",
                existe=True,
                resuelto_como=None,
                deprecacion=None,
                deprecados=[_query_get_deprecado()],
            )
        ]
    )
    assert "DEPRECADO" in salida
    assert "sqlalchemy.orm.Query.get" in salida
    assert "Session.get" in salida  # el reemplazo
