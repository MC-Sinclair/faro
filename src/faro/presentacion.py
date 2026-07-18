"""Convierte objetos de dominio en el texto que ve el asistente.

Toda la cosmética vive acá. El núcleo no formatea.
"""

import re

from faro.dominio import Ambiguo, Deprecacion, Fragmento, NoEncontrado, Verificacion

TOPE_CARACTERES = 4000

# Un símbolo puede existir sin declarar documentación. Decirlo explícitamente evita
# que el lector confunda "no hay doc" con "Faro falló" o "el símbolo no existe".
SIN_DOCUMENTACION = "[este símbolo no declara documentación]"

# :class:`_engine.Result` -> Result ; :meth:`~_orm.Session.get` -> Session.get
_ROL_RST = re.compile(r":(?:class|meth|func|attr|mod|ref|term|paramref):`~?_?([\w.]+)`")


def _aviso_de_deprecacion(d: Deprecacion) -> str:
    """El aviso, con un espacio al principio para pegarlo a lo que venga antes."""
    aviso = f"  ⚠ DEPRECADO desde {d.desde}"
    if d.reemplazo:
        aviso += f" — usar {d.reemplazo}"
    return aviso


def limpiar_rst(texto: str) -> str:
    """Quita el markup de Sphinx, dejando el nombre legible."""

    def _nombre(m: re.Match[str]) -> str:
        return m.group(1).split(".")[-1]

    return _ROL_RST.sub(_nombre, texto)


def formatear(r: Fragmento | Ambiguo | NoEncontrado) -> str:
    if isinstance(r, NoEncontrado):
        return f"NO ENCONTRADO. {r.motivo}"

    if isinstance(r, Ambiguo):
        avisos = {d.nombre: _aviso_de_deprecacion(d.deprecacion) for d in r.deprecados}
        lineas = [
            f"AMBIGUO: '{r.consulta}' resuelve a varios símbolos. Pedí uno concreto:",
            *(f"  - {c}{avisos.get(c, '')}" for c in r.candidatos),
        ]
        return "\n".join(lineas)

    lineas = [f"{r.libreria} {r.version} :: {r.simbolo}"]

    if r.deprecacion is not None:
        lineas.append(_aviso_de_deprecacion(r.deprecacion).lstrip())

    if r.firma is not None:
        lineas.append(f"{r.simbolo.rsplit('.', 1)[-1]}{r.firma}")

    lineas.append("")
    if r.texto is None:
        lineas.append(SIN_DOCUMENTACION)
    else:
        lineas.append(_recortar(limpiar_rst(r.texto)))
    return "\n".join(lineas)


def formatear_verificaciones(vs: list[Verificacion]) -> str:
    lineas = []
    for v in vs:
        if not v.existe:
            lineas.append(f"{v.simbolo}: NO EXISTE en esta versión.")
            continue

        linea = f"{v.simbolo}: existe"
        if v.resuelto_como:
            linea += f" ({v.resuelto_como})"
        else:
            linea += " (ambiguo: varios símbolos coinciden)"

        if v.deprecacion is not None:
            linea += f" — ⚠ DEPRECADO desde {v.deprecacion.desde}"
            if v.deprecacion.reemplazo:
                linea += f", usar {v.deprecacion.reemplazo}"
        if v.deprecados:
            # Ambiguo: no elegimos, pero decimos cuáles opciones son trampas.
            detalles = ", ".join(
                d.nombre + (f" (usar {d.deprecacion.reemplazo})" if d.deprecacion.reemplazo else "")
                for d in v.deprecados
            )
            linea += f" — ⚠ {len(v.deprecados)} candidatos DEPRECADOS: {detalles}"
        if v.firma is not None and v.resuelto_como is not None:
            linea += f" — {v.resuelto_como.rsplit('.', 1)[-1]}{v.firma}"
        lineas.append(linea)
    return "\n".join(lineas)


def _recortar(texto: str) -> str:
    if len(texto) <= TOPE_CARACTERES:
        return texto
    return texto[:TOPE_CARACTERES] + "\n\n[... recortado: el docstring completo es más largo]"
