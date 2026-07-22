# Símbolos ajenos atribuidos a la librería — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faro deja de citar símbolos ajenos (importados, no definidos) como si fueran de la librería consultada — en vez de ocultarlos, anota su origen real.

**Architecture:** Un campo nuevo, `modulo_origen`, calculado en `extractor.py` (única pieza con el objeto vivo y su `__module__`), viaja sin transformación por `EntradaSimbolo` → `Fragmento`/`Verificacion` → texto formateado. El núcleo no gana lógica nueva, solo propaga un dato más.

**Tech Stack:** Python 3.12, `uv`, `pytest` (marker `contrato` para tests contra SQLAlchemy/Faro reales).

## Global Constraints

- El núcleo (`resolver.py`, `dominio.py`, `parseo.py`, `catalogo.py`) no importa `subprocess`, `httpx` ni `mcp`. `extractor.py` solo usa stdlib y no importa nada de `faro`.
- Todo en español: código, tests, commits.
- `Fragmento.modulo_origen` es obligatorio (sin default) — mismo trato que `libreria`/`version`/`simbolo`. `Verificacion.modulo_origen` es opcional con default `None` — mismo trato que `firma`.
- El origen de un método heredado es SIEMPRE el de la clase que lo expone (`origen_clase`), nunca el `__module__` de la base física donde el método vive.
- `__module__` ausente o vacío cae a la librería consultada (se asume propio sin evidencia de lo contrario).
- No se resuelve la versión del módulo de origen ajeno — solo su nombre.
- Commits frecuentes, uno por tarea, formato imperativo en español, con `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

---

### Task 1: `extractor.py` — calcular y emitir `modulo_origen`

**Files:**
- Modify: `src/faro/fuentes/extractor.py`
- Create: `tests/fixtures_extractor_dedupe/otro_paquete/__init__.py`
- Modify: `tests/fixtures_extractor_dedupe/paquete_prueba/base.py`
- Test: `tests/test_extractor.py`

**Interfaces:**
- Consumes: nada nuevo (extractor.py no depende de ningún módulo de `faro`).
- Produces: `extraer(libreria: str, modulos: list[str]) -> list[dict]` — firma cambiada, gana el parámetro `libreria`. Cada dict de salida gana la clave `"modulo_origen": str`. `main()` ya no llama `extraer(modulos)`, llama `extraer(libreria, modulos)`.

- [ ] **Step 1: Crear el paquete fixture "ajeno"**

Crear `tests/fixtures_extractor_dedupe/otro_paquete/__init__.py`:

```python
"""Paquete ajeno de prueba: simula una librería de terceros de la que otra
librería importa una clase sin ser su dueña."""


class BaseAjena:
    def metodo_ajena(self):
        """Doc de metodo_ajena, definido en otro_paquete."""
```

- [ ] **Step 2: Hacer que `paquete_prueba` importe de esa librería ajena**

Editar `tests/fixtures_extractor_dedupe/paquete_prueba/base.py`, agregando al final del archivo (después de `SinDocumentar`):

```python
from otro_paquete import BaseAjena as BaseAjena


class HeredaDeAjena(BaseAjena):
    """Hereda de una clase de otro_paquete: sus métodos heredados deben seguir
    marcándose como propios de paquete_prueba (spec 2026-07-19)."""
```

(El import va al final del archivo junto a la clase que lo usa, no al principio, para no reordenar el resto del archivo existente y mantener el diff mínimo.)

- [ ] **Step 3: Escribir los tests que fallan**

Agregar a `tests/test_extractor.py` (al final del archivo):

```python
def test_simbolo_propio_declara_su_propia_libreria_como_origen():
    r = _correr({"libreria": "textwrap", "modulos": ["textwrap"]})
    por_nombre = {s["nombre"]: s for s in r["simbolos"]}
    assert por_nombre["textwrap.dedent"]["modulo_origen"] == "textwrap"


def test_simbolo_top_level_ajeno_declara_su_libreria_real():
    """BaseAjena vive en otro_paquete pero se importa en paquete_prueba.base:
    su origen debe ser 'otro_paquete', no 'paquete_prueba'."""
    r = _correr(
        {"libreria": "paquete_prueba", "modulos": ["paquete_prueba.base"]},
        env=_env_con_fixture_dedupe(),
    )
    por_nombre = {s["nombre"]: s for s in r["simbolos"]}
    assert por_nombre["paquete_prueba.base.BaseAjena"]["modulo_origen"] == "otro_paquete"


def test_metodo_heredado_de_clase_ajena_se_atribuye_a_la_clase_duena():
    """HeredaDeAjena es propia de paquete_prueba aunque su base (BaseAjena) sea
    de otro_paquete: el método heredado debe marcarse propio de paquete_prueba,
    no de otro_paquete — decisión de diseño explícita (spec 2026-07-19)."""
    r = _correr(
        {"libreria": "paquete_prueba", "modulos": ["paquete_prueba.base"]},
        env=_env_con_fixture_dedupe(),
    )
    por_nombre = {s["nombre"]: s for s in r["simbolos"]}
    clave = "paquete_prueba.base.HeredaDeAjena.metodo_ajena"
    assert clave in por_nombre
    assert por_nombre[clave]["modulo_origen"] == "paquete_prueba"
```

- [ ] **Step 4: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/test_extractor.py -k "modulo_origen or top_level_ajeno or heredado_de_clase_ajena" -v`
Expected: FAIL — `KeyError: 'modulo_origen'` (la clave todavía no existe en el dict de salida).

- [ ] **Step 5: Implementar `_raiz_modulo` y enhebrar `modulo_origen`**

Reemplazar en `src/faro/fuentes/extractor.py` la función `extraer` completa (líneas 48-86 del archivo actual) por:

```python
def extraer(libreria: str, modulos: list[str]) -> list[dict[str, str]]:
    """Muchas librerías re-exportan la misma clase/función en el paquete raíz y en
    su submódulo real (p. ej. sqlalchemy.Connection es sqlalchemy.engine.Connection).
    Si contáramos ambas rutas como símbolos distintos, cualquier consulta sin
    calificar (p. ej. "Connection.execute") saldría ambigua por error: no hay dos
    símbolos, hay uno solo con dos nombres. Por eso se procesan primero los módulos
    con path más específico (tienen un punto) y se deduplica por identidad
    (`is`): la primera vez que se ve un objeto gana su nombre calificado, y las
    apariciones posteriores del MISMO objeto bajo otro nombre se ignoran.
    """
    vistos: dict[str, dict[str, str | None]] = {}
    nombre_elegido: dict[int, str] = {}

    for nombre_modulo in sorted(modulos, key=lambda m: m.count(".") == 0):
        try:
            modulo = importlib.import_module(nombre_modulo)
        except Exception:
            # Un módulo que no importa no debe tumbar la extracción de los demás.
            continue

        for nombre, objeto in vars(modulo).items():
            if nombre.startswith("_"):
                continue

            if inspect.isclass(objeto):
                if id(objeto) in nombre_elegido:
                    continue  # re-export: ya se registró vía un módulo más específico
                nombre_elegido[id(objeto)] = f"{nombre_modulo}.{nombre}"
                origen = _raiz_modulo(objeto, libreria)
                _anotar(vistos, f"{nombre_modulo}.{nombre}", objeto, modulo_origen=origen)
                _anotar_miembros(vistos, f"{nombre_modulo}.{nombre}", objeto, origen)
            elif inspect.isfunction(objeto):
                if id(objeto) in nombre_elegido:
                    continue
                nombre_elegido[id(objeto)] = f"{nombre_modulo}.{nombre}"
                origen = _raiz_modulo(objeto, libreria)
                _anotar(vistos, f"{nombre_modulo}.{nombre}", objeto, modulo_origen=origen)

    return [
        {
            "nombre": n,
            "doc": v["doc"],
            "firma": v["firma"],
            "modulo_origen": v["modulo_origen"],
        }
        for n, v in sorted(vistos.items())
    ]


def _raiz_modulo(objeto: object, libreria: str) -> str:
    """Primer componente de __module__: la librería que define `objeto` de verdad.

    Puede faltar o ser raro en extensiones C y algunos builtins — de ahí el
    `getattr(..., "") or ""`. Sin `__module__` legible, no hay evidencia de que
    el símbolo sea ajeno: se asume propio de `libreria` (el mismo trato que
    tenía TODO símbolo antes de este cambio).
    """
    origen = (getattr(objeto, "__module__", "") or "").split(".")[0]
    return origen or libreria
```

Reemplazar la función `_anotar_miembros` (líneas 108-135 del archivo actual) por:

```python
def _anotar_miembros(
    vistos: dict[str, dict[str, str | None]], nombre_clase: str, clase: type, origen_clase: str
) -> None:
    """Recorre toda la cadena de herencia (__mro__), no solo vars(clase) propia.

    Un método heredado y no sobreescrito (p. ej. CursorResult.fetchall, que vive
    en Result) no aparece en vars(CursorResult) — sin este recorrido, el extractor
    lo reporta como inexistente aunque exista de verdad. Python coloca la propia
    clase primero en __mro__, así que "la primera vez que se ve el nombre gana"
    reproduce la misma regla de resolución de atributos de Python: una subclase
    que sobreescribe gana con su propio docstring; si no sobreescribe, gana la
    versión de la clase base donde el método realmente vive.

    `origen_clase` es el origen YA calculado de la clase dueña (nombre_clase), y
    se propaga a TODO miembro heredado sin recalcularlo por atributo: un método
    heredado de una base ajena (p. ej. Path.cwd, con Path entero ajeno a quien
    lo importa) se anota con el origen de la clase que lo expone, no con el
    __module__ de la base física donde vive — decisión de diseño explícita, ver
    docs/superpowers/specs/2026-07-19-faro-simbolos-ajenos-design.md.
    """
    ya_vistos: set[str] = set()
    for base in clase.__mro__:
        for nombre_attr, attr in vars(base).items():
            if nombre_attr.startswith("_") or nombre_attr in ya_vistos:
                continue
            if (
                inspect.isfunction(attr)
                or isinstance(attr, property)
                or isinstance(attr, (classmethod, staticmethod))
            ):
                ya_vistos.add(nombre_attr)
                _anotar(
                    vistos,
                    f"{nombre_clase}.{nombre_attr}",
                    attr,
                    modulo_origen=origen_clase,
                    objeto_firma=getattr(base, nombre_attr),
                )
```

Reemplazar la función `_anotar` (líneas 138-159 del archivo actual) por:

```python
def _anotar(
    vistos: dict[str, dict[str, str | None]],
    nombre: str,
    objeto_doc: object,
    modulo_origen: str,
    objeto_firma: object | None = None,
) -> None:
    """Registra el símbolo exista o no su docstring.

    Que un símbolo no declare documentación NO significa que no exista: son dos
    afirmaciones distintas, y Faro solo sabe la primera. Descartarlo acá hacía que
    el propio Faro reportara como inexistentes 2 de sus 3 herramientas MCP.
    """
    if nombre in vistos:
        return
    try:
        doc = inspect.getdoc(objeto_doc)
    except Exception:
        doc = None  # que getdoc falle tampoco significa que el símbolo no exista
    vistos[nombre] = {
        "doc": doc,
        "firma": _firma_de(objeto_firma if objeto_firma is not None else objeto_doc),
        "modulo_origen": modulo_origen,
    }
```

Por último, en `main()` (cerca del final del archivo), cambiar:

```python
    simbolos = extraer(modulos) if version is not None else []
```

por:

```python
    simbolos = extraer(libreria, modulos) if version is not None else []
```

- [ ] **Step 6: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/test_extractor.py -v`
Expected: PASS — todos, incluidos los 3 nuevos y los ya existentes (herencia, dedupe, firmas, etc. no deben regresionar).

- [ ] **Step 7: Commit**

```bash
git add src/faro/fuentes/extractor.py tests/test_extractor.py tests/fixtures_extractor_dedupe/otro_paquete/ tests/fixtures_extractor_dedupe/paquete_prueba/base.py
git commit -m "$(cat <<'EOF'
feat: el extractor calcula el módulo de origen real de cada símbolo

Faro atribuía a una librería símbolos que solo estaban importados ahí, no
definidos (p. ej. pathlib.Path dentro de faro.fuentes.local). Cada símbolo
ahora lleva modulo_origen: la raíz de __module__ del objeto. Los métodos
heredados toman el origen de la clase que los expone, no el de la base
física donde viven — así Path.cwd (Path entero ajeno) se marca ajeno, y un
método heredado de una base ajena por una clase propia sigue siendo propio.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `dominio.py` — el modelo declara el origen

**Files:**
- Modify: `src/faro/dominio.py`
- Test: `tests/test_dominio.py`

**Interfaces:**
- Consumes: nada (dominio.py no depende de extractor.py).
- Produces: `EntradaSimbolo.modulo_origen: str` (obligatorio). `Fragmento.modulo_origen: str` (obligatorio). `Verificacion.modulo_origen: str | None = None` (opcional, default `None`).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_dominio.py` (al final del archivo):

```python
def test_un_fragmento_declara_su_origen_real():
    """El caso que funda esta spec: un símbolo puede existir bajo una librería
    sin ser SUYO — Faro debe poder decir cuál es su origen real."""
    f = Fragmento(
        libreria="faro",
        version="0.1.0",
        simbolo="faro.fuentes.local.Path.cwd",
        texto="doc",
        deprecacion=None,
        modulo_origen="pathlib",
    )
    assert f.modulo_origen == "pathlib"
    assert f.modulo_origen != f.libreria
```

Y modificar las dos construcciones de `Fragmento` ya existentes en el mismo archivo para que sigan compilando (van a fallar con `TypeError: missing ... argument` hasta el Step 3):

`test_un_fragmento_lleva_su_procedencia_dentro` (líneas 13-24):

```python
def test_un_fragmento_lleva_su_procedencia_dentro():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session.execute",
        texto="Execute a SQL expression construct.",
        deprecacion=None,
        modulo_origen="sqlalchemy",
    )
    assert f.libreria == "sqlalchemy"
    assert f.version == "2.0.36"
    assert f.simbolo == "sqlalchemy.orm.Session.execute"
```

`test_un_fragmento_es_inmutable` (líneas 26-35):

```python
def test_un_fragmento_es_inmutable():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="x.y",
        texto="doc",
        deprecacion=None,
        modulo_origen="sqlalchemy",
    )
    with pytest.raises(FrozenInstanceError):
        f.version = "1.4"  # type: ignore[misc]
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/test_dominio.py -v`
Expected: FAIL — `TypeError: Fragmento.__init__() got an unexpected keyword argument 'modulo_origen'`.

- [ ] **Step 3: Implementar los campos**

En `src/faro/dominio.py`, reemplazar la clase `EntradaSimbolo` completa por:

```python
@dataclass(frozen=True)
class EntradaSimbolo:
    """Un símbolo tal como lo devuelve una FuenteDeDocs, sin interpretar.

    `doc` puede ser None: hay símbolos que existen y no declaran documentación.
    No tener doc no es no existir. `modulo_origen` es la raíz de __module__ del
    objeto: la librería que REALMENTE lo define, que puede no ser la librería
    consultada (p. ej. pathlib.Path importado dentro de otro paquete).
    """

    nombre: str
    doc: str | None
    deprecacion: Deprecacion | None
    modulo_origen: str
    firma: str | None = None
```

Reemplazar la clase `Fragmento` completa por:

```python
@dataclass(frozen=True)
class Fragmento:
    """Una respuesta de Faro. Lleva su procedencia dentro.

    `texto` puede ser None (símbolo sin documentación declarada) — no debilita la
    regla 2: la garantía estructural es sobre libreria/version/simbolo, y `texto`
    sigue siendo obligatorio de construir, solo que su valor puede ser nulo.
    `modulo_origen` es la librería que REALMENTE define `simbolo` (raíz de
    __module__): puede ser distinta de `libreria` cuando el símbolo solo está
    importado ahí, no definido (p. ej. pathlib.Path dentro de otro paquete). Es
    obligatorio, igual que libreria/version/simbolo: nunca hay Fragmento sin
    saber de dónde sale de verdad el símbolo.
    """

    libreria: str
    version: str
    simbolo: str
    texto: str | None
    deprecacion: Deprecacion | None
    modulo_origen: str
    firma: str | None = None
```

Reemplazar la clase `Verificacion` completa por:

```python
@dataclass(frozen=True)
class Verificacion:
    """El veredicto sobre un símbolo afirmado por alguien (modelo, blog, otro MCP).

    `deprecacion` (singular) es "el símbolo que pediste, resuelto sin ambigüedad,
    está deprecado". `deprecados` (plural) es "algunas de las varias cosas que tu
    consulta podría significar lo están" — situaciones distintas, y en la segunda
    puede haber varios reemplazos, así que colapsarlas obligaría a elegir uno.
    `modulo_origen` sigue el mismo patrón que `firma`/`resuelto_como`: solo tiene
    sentido cuando la consulta resolvió a un único símbolo, así que es None en
    los casos "no existe" y "ambiguo" (no hay un origen único que afirmar).
    """

    simbolo: str
    existe: bool
    resuelto_como: str | None
    deprecacion: Deprecacion | None
    firma: str | None = None
    modulo_origen: str | None = None
    deprecados: list[CandidatoDeprecado] = field(default_factory=list)
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/test_dominio.py -v`
Expected: PASS — los 3 tests de Fragmento y los demás (Ambiguo, NoEncontrado) sin tocar.

- [ ] **Step 5: Commit**

```bash
git add src/faro/dominio.py tests/test_dominio.py
git commit -m "$(cat <<'EOF'
feat: el dominio modela el origen real de un símbolo

EntradaSimbolo y Fragmento ganan modulo_origen (obligatorio, como
libreria/version/simbolo: nunca hay una cita sin saber de dónde sale el
símbolo de verdad). Verificacion lo gana como opcional con default None,
mismo patrón que firma/resuelto_como — solo tiene sentido cuando la
consulta resolvió a un único símbolo.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `fake.py` — los fixtures declaran su origen real

**Files:**
- Modify: `src/faro/fuentes/fake.py`
- Test: `tests/test_fuente_fake.py`

**Interfaces:**
- Consumes: `EntradaSimbolo` de Task 2 (con `modulo_origen` obligatorio).
- Produces: `simbolos_de_prueba()` sigue devolviendo `list[EntradaSimbolo]`, ahora cada entrada con `modulo_origen="sqlalchemy"`.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_fuente_fake.py` (al final del archivo):

```python
def test_los_simbolos_de_prueba_son_propios_de_sqlalchemy():
    """Son símbolos reales de SQLAlchemy: su origen declarado debe ser la propia
    librería, no otra."""
    assert all(e.modulo_origen == "sqlalchemy" for e in simbolos_de_prueba())
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `uv run pytest tests/test_fuente_fake.py -v`
Expected: FAIL — `TypeError: EntradaSimbolo.__init__() missing 1 required positional argument: 'modulo_origen'` (falla al construir `simbolos_de_prueba()` porque `fake.py` todavía no pasa el campo).

- [ ] **Step 3: Agregar `modulo_origen="sqlalchemy"` a las 6 entradas**

En `src/faro/fuentes/fake.py`, `simbolos_de_prueba()` queda:

```python
def simbolos_de_prueba() -> list[EntradaSimbolo]:
    """Un puñado de símbolos reales de SQLAlchemy 2.0.36."""
    return [
        EntradaSimbolo(
            nombre="sqlalchemy.orm.Session.execute",
            doc="Execute a SQL expression construct.",
            deprecacion=None,
            modulo_origen="sqlalchemy",
            firma="(statement, params=None, *, execution_options={})",
        ),
        EntradaSimbolo(
            nombre="sqlalchemy.orm.Session.get",
            doc="Return an instance based on the given primary key identifier.",
            deprecacion=None,
            modulo_origen="sqlalchemy",
        ),
        EntradaSimbolo(
            nombre="sqlalchemy.orm.Query.get",
            doc="Return an instance based on the given primary key identifier, or None if not found.",
            deprecacion=Deprecacion(
                desde="2.0",
                mensaje=(
                    "The Query.get method is considered legacy as of the 1.x series of "
                    "SQLAlchemy and becomes a legacy construct in 2.0. The method is now "
                    "available as Session.get"
                ),
                reemplazo="Session.get",
            ),
            modulo_origen="sqlalchemy",
        ),
        # Existe de verdad en 2.0.36 y NO tiene docstring: el extractor lo descartaba
        # entero, haciendo que Faro lo reportara como inexistente.
        EntradaSimbolo(
            nombre="sqlalchemy.engine.Connection.commit_prepared",
            doc=None,
            deprecacion=None,
            modulo_origen="sqlalchemy",
            firma="(xid, recover=False)",
        ),
        # Dos símbolos que colisionan por sufijo: fuerzan el camino Ambiguo.
        EntradaSimbolo(
            nombre="sqlalchemy.sql.expression.Select.select",
            doc="Legacy select.",
            deprecacion=None,
            modulo_origen="sqlalchemy",
        ),
        EntradaSimbolo(
            nombre="sqlalchemy.schema.Table.select",
            doc="Return a SELECT of this Table.",
            deprecacion=None,
            modulo_origen="sqlalchemy",
        ),
    ]
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/test_fuente_fake.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/faro/fuentes/fake.py tests/test_fuente_fake.py
git commit -m "$(cat <<'EOF'
test: los fixtures de SQLAlchemy declaran su origen real

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `local.py` — cablear `modulo_origen` desde el JSON del extractor

**Files:**
- Modify: `src/faro/fuentes/local.py`
- Test: `tests/test_fuente_local.py`

**Interfaces:**
- Consumes: `extractor.py` (Task 1) — cada símbolo del JSON trae `"modulo_origen": str`. `EntradaSimbolo` (Task 2).
- Produces: `FuenteLocal.simbolos(libreria) -> list[EntradaSimbolo]` con `modulo_origen` poblado desde el JSON crudo.

- [ ] **Step 1: Escribir el test que falla**

En `tests/test_fuente_local.py`, agregar los imports que faltan al principio del archivo:

```python
import os
import subprocess
import sys
from pathlib import Path

import pytest

from faro.fuentes.local import FuenteLocal
```

(reemplaza el bloque de imports actual, que no tiene `os` ni `Path`).

Agregar al final del archivo:

```python
def test_modulo_origen_distingue_lo_propio_de_lo_ajeno(monkeypatch):
    """Cableado completo extractor→FuenteLocal: BaseAjena vive en otro_paquete
    pero se importa en paquete_prueba.base — su origen real debe llegar intacto
    hasta EntradaSimbolo, distinto del origen de un símbolo genuinamente propio."""
    fixtures = Path(__file__).parent / "fixtures_extractor_dedupe"
    monkeypatch.setenv(
        "PYTHONPATH", str(fixtures) + os.pathsep + os.environ.get("PYTHONPATH", "")
    )
    fuente = FuenteLocal(python=sys.executable)
    por_nombre = {e.nombre: e for e in fuente.simbolos("paquete_prueba")}

    assert por_nombre["paquete_prueba.base.Cosa.metodo"].modulo_origen == "paquete_prueba"
    assert por_nombre["paquete_prueba.base.BaseAjena"].modulo_origen == "otro_paquete"
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `uv run pytest tests/test_fuente_local.py -k modulo_origen -v`
Expected: FAIL — `KeyError: 'modulo_origen'` en `local.py` al construir `EntradaSimbolo` desde el dict crudo.

- [ ] **Step 3: Implementar**

En `src/faro/fuentes/local.py`, reemplazar el método `simbolos`:

```python
    def simbolos(self, libreria: str) -> list[EntradaSimbolo]:
        crudos = self._extraer(libreria)["simbolos"]
        return [
            EntradaSimbolo(
                nombre=s["nombre"],
                doc=s["doc"],
                firma=s.get("firma"),
                modulo_origen=s["modulo_origen"],
                deprecacion=extraer_deprecacion(s["doc"]),
            )
            for s in crudos
        ]
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/test_fuente_local.py -v`
Expected: PASS — todos, incluido el nuevo.

- [ ] **Step 5: Commit**

```bash
git add src/faro/fuentes/local.py tests/test_fuente_local.py
git commit -m "$(cat <<'EOF'
feat: FuenteLocal propaga el origen real de cada símbolo

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `resolver.py` — el origen llega a `Fragmento` y `Verificacion`

**Files:**
- Modify: `src/faro/resolver.py`
- Test: `tests/test_resolver_buscar.py`
- Test: `tests/test_resolver_verificar.py`

**Interfaces:**
- Consumes: `EntradaSimbolo.modulo_origen` (Task 2/3).
- Produces: `ResolverDeDocs.buscar_doc(...)` devuelve `Fragmento` con `modulo_origen` poblado. `ResolverDeDocs.verificar_simbolos(...)` devuelve `Verificacion` con `modulo_origen` poblado solo cuando resuelve a un único símbolo (`None` si es ambiguo o no existe).

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_resolver_buscar.py`, cambiar el import del principio:

```python
from faro.dominio import Ambiguo, EntradaSimbolo, Fragmento, NoEncontrado
```

Agregar al final del archivo:

```python
def test_el_fragmento_arrastra_el_origen_propio(resolver):
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Session.execute")
    assert isinstance(r, Fragmento)
    assert r.modulo_origen == "sqlalchemy"


def test_el_fragmento_declara_un_origen_ajeno():
    """El caso fundacional de esta spec: un símbolo que solo está importado en
    la librería consultada, no definido ahí (p. ej. pathlib.Path en faro)."""
    entradas = [
        EntradaSimbolo(
            nombre="faro.fuentes.local.Path.cwd",
            doc="Return a new path pointing to the current working directory.",
            deprecacion=None,
            modulo_origen="pathlib",
            firma="()",
        )
    ]
    resolver_faro = ResolverDeDocs(FuenteFake(version="0.1.0", entradas=entradas, libreria="faro"))
    r = resolver_faro.buscar_doc("faro", "0.1.0", "Path.cwd")
    assert isinstance(r, Fragmento)
    assert r.modulo_origen == "pathlib"
    assert r.modulo_origen != r.libreria
```

En `tests/test_resolver_verificar.py`, cambiar el import del principio:

```python
from faro.dominio import EntradaSimbolo, NoEncontrado
```

Agregar al final del archivo:

```python
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
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/test_resolver_buscar.py tests/test_resolver_verificar.py -v`
Expected: FAIL — `assert None == "sqlalchemy"` (resolver todavía no pasa `modulo_origen` a `Fragmento`/`Verificacion`, así que quedan en su default `None`, o directamente `TypeError` si `Fragmento` no tiene default para el campo — en este caso, como `Fragmento.modulo_origen` no tiene default, resolver.py fallará con `TypeError: missing ... 'modulo_origen'` al construir el Fragmento).

- [ ] **Step 3: Implementar**

En `src/faro/resolver.py`, en `buscar_doc`, reemplazar el `return Fragmento(...)` final:

```python
        entrada = candidatos[0]
        return Fragmento(
            libreria=libreria,
            version=instalada,
            simbolo=entrada.nombre,
            texto=entrada.doc,
            deprecacion=entrada.deprecacion,
            modulo_origen=entrada.modulo_origen,
            firma=entrada.firma,
        )
```

En `verificar_simbolos`, reemplazar la rama del único candidato (el bloque `else:` final del `for simbolo in simbolos:`):

```python
            else:
                e = candidatos[0]
                veredictos.append(
                    Verificacion(
                        simbolo=simbolo,
                        existe=True,
                        resuelto_como=e.nombre,
                        deprecacion=e.deprecacion,
                        firma=e.firma,
                        modulo_origen=e.modulo_origen,
                    )
                )
```

(Las ramas "no existe" y "ambiguo" no se tocan: ya no pasan `modulo_origen`, así que usan el default `None` de `Verificacion`, que es exactamente lo que corresponde.)

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/test_resolver_buscar.py tests/test_resolver_verificar.py -v`
Expected: PASS — todos, incluidos los ya existentes (deprecaciones, ambigüedad, guarda de versión).

- [ ] **Step 5: Commit**

```bash
git add src/faro/resolver.py tests/test_resolver_buscar.py tests/test_resolver_verificar.py
git commit -m "$(cat <<'EOF'
feat: el resolver propaga el origen real a Fragmento y Verificacion

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: `presentacion.py` + `servidor.py` — mostrar el origen en el texto

**Files:**
- Modify: `src/faro/presentacion.py`
- Modify: `src/faro/servidor.py`
- Test: `tests/test_presentacion.py`

**Interfaces:**
- Consumes: `Fragmento.modulo_origen`, `Verificacion.modulo_origen` (Task 2/5).
- Produces: `formatear(r) -> str` sin cambio de firma, agrega una línea "definido en: ...". `formatear_verificaciones(vs: list[Verificacion], libreria: str) -> str` — **cambia de firma**, gana el parámetro `libreria` (obligatorio, sin default).

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_presentacion.py`, aplicar estos reemplazos completos (cada función queda exactamente así):

```python
def test_la_cita_siempre_aparece():
    """Regla 2: librería, versión y símbolo, siempre."""
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session.execute",
        texto="Execute a SQL expression construct.",
        deprecacion=None,
        modulo_origen="sqlalchemy",
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
        modulo_origen="sqlalchemy",
    )
    salida = formatear(f)
    assert "DEPRECADO" in salida
    assert "Session.get" in salida
```

```python
def test_recorta_los_docstrings_gigantes():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session",
        texto="x" * 20_000,
        deprecacion=None,
        modulo_origen="sqlalchemy",
    )
    salida = formatear(f)
    assert len(salida) < TOPE_CARACTERES + 500
    assert "recortado" in salida
```

```python
def test_las_verificaciones_marcan_lo_que_no_existe():
    vs = [
        Verificacion(simbolo="Session.execute", existe=True, resuelto_como="x.Session.execute", deprecacion=None),
        Verificacion(simbolo="Session.inventado", existe=False, resuelto_como=None, deprecacion=None),
    ]
    salida = formatear_verificaciones(vs, libreria="x")
    assert "NO EXISTE" in salida
```

```python
def test_la_firma_aparece_si_esta_presente():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session.execute",
        texto="Execute a SQL expression construct.",
        deprecacion=None,
        modulo_origen="sqlalchemy",
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
        modulo_origen="sqlalchemy",
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
    salida = formatear_verificaciones(vs, libreria="sqlalchemy")
    assert "(statement, parameters=None)" in salida


def test_verificacion_sin_firma_no_agrega_nada_de_mas():
    con_firma_none = Verificacion(
        simbolo="Session.execute", existe=True, resuelto_como="x.Session.execute", deprecacion=None
    )
    assert formatear_verificaciones([con_firma_none], libreria="x") == "Session.execute: existe (x.Session.execute)"


def test_un_simbolo_sin_documentacion_lo_dice_y_conserva_cita_y_firma():
    f = Fragmento(
        libreria="faro",
        version="0.1.0",
        simbolo="faro.resolver.ResolverDeDocs.buscar_doc",
        texto=None,
        deprecacion=None,
        modulo_origen="faro",
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
        modulo_origen="sqlalchemy",
    )
    assert "no declara documentación" not in formatear(f)
```

```python
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
        ],
        libreria="sqlalchemy",
    )
    assert "DEPRECADO" in salida
    assert "sqlalchemy.orm.Query.get" in salida
    assert "Session.get" in salida  # el reemplazo
```

Y agregar, al final del archivo, los tests nuevos que prueban específicamente esta spec:

```python
def test_fragmento_propio_dice_definido_en_su_propia_libreria():
    f = Fragmento(
        libreria="sqlalchemy",
        version="2.0.36",
        simbolo="sqlalchemy.orm.Session.execute",
        texto="doc",
        deprecacion=None,
        modulo_origen="sqlalchemy",
    )
    salida = formatear(f)
    assert "definido en: sqlalchemy 2.0.36" in salida


def test_fragmento_ajeno_dice_de_donde_viene_de_verdad():
    """El caso fundacional de esta spec: Path.cwd existe en faro pero no es
    de faro — la cita no debe mentir sobre quién lo define."""
    f = Fragmento(
        libreria="faro",
        version="0.1.0",
        simbolo="faro.fuentes.local.Path.cwd",
        texto="doc",
        deprecacion=None,
        modulo_origen="pathlib",
    )
    salida = formatear(f)
    assert "definido en: pathlib (no en faro 0.1.0)" in salida


def test_verificacion_propia_no_agrega_sufijo_de_origen():
    v = Verificacion(
        simbolo="Session.execute",
        existe=True,
        resuelto_como="sqlalchemy.orm.Session.execute",
        deprecacion=None,
        modulo_origen="sqlalchemy",
    )
    assert formatear_verificaciones([v], libreria="sqlalchemy") == (
        "Session.execute: existe (sqlalchemy.orm.Session.execute)"
    )


def test_verificacion_ajena_agrega_el_origen():
    v = Verificacion(
        simbolo="Path.cwd",
        existe=True,
        resuelto_como="faro.fuentes.local.Path.cwd",
        deprecacion=None,
        modulo_origen="pathlib",
    )
    salida = formatear_verificaciones([v], libreria="faro")
    assert "definido en pathlib, no en faro" in salida
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/test_presentacion.py -v`
Expected: FAIL — `TypeError: formatear_verificaciones() missing 1 required positional argument: 'libreria'` en los tests que ya pasan `libreria=...`, y `AssertionError` en los tests nuevos de origen (la línea "definido en" todavía no existe).

- [ ] **Step 3: Implementar**

En `src/faro/presentacion.py`, reemplazar `formatear`:

```python
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

    if r.modulo_origen == r.libreria:
        lineas.append(f"definido en: {r.libreria} {r.version}")
    else:
        lineas.append(f"definido en: {r.modulo_origen} (no en {r.libreria} {r.version})")

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
```

Reemplazar `formatear_verificaciones`:

```python
def formatear_verificaciones(vs: list[Verificacion], libreria: str) -> str:
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
        if v.modulo_origen is not None and v.modulo_origen != libreria:
            linea += f" — definido en {v.modulo_origen}, no en {libreria}"
        lineas.append(linea)
    return "\n".join(lineas)
```

En `src/faro/servidor.py`, en la función `verificar_simbolos`, reemplazar:

```python
    return formatear_verificaciones(r) + _aviso_de_entorno()
```

por:

```python
    return formatear_verificaciones(r, libreria) + _aviso_de_entorno()
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/test_presentacion.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Correr toda la suite rápida**

Run: `uv run pytest -m "not contrato" -v`
Expected: PASS — sin regresiones en ningún módulo (extractor, dominio, resolver, presentación, fuentes, servidor).

- [ ] **Step 6: Commit**

```bash
git add src/faro/presentacion.py src/faro/servidor.py tests/test_presentacion.py
git commit -m "$(cat <<'EOF'
feat: mostrar el origen real de un símbolo en el texto

buscar_doc siempre dice "definido en: X Y" (propio) o "definido en: X (no
en Y Z)" (ajeno) — regla 2 extendida: la cita nunca implica que Faro
controla la versión de algo que no define. verificar_simbolos agrega el
origen solo cuando es ajeno, para no saturar el formato de una línea con
información redundante en el caso común (símbolo propio).

formatear_verificaciones gana el parámetro libreria: Verificacion no lo
lleva (evita repetirlo en cada elemento de una lista ya scopeada a una
sola consulta), así que hace falta pasarlo para decidir propio/ajeno.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Tests de contrato — verificar contra SQLAlchemy y Faro reales

**Files:**
- Modify: `tests/test_contrato.py`

**Interfaces:**
- Consumes: todo el pipeline real (`FuenteLocal` + `ResolverDeDocs`), sin fakes.
- Produces: nada nuevo — solo tests.

- [ ] **Step 1: Escribir los tests**

Agregar a `tests/test_contrato.py` (al final del archivo):

```python
def test_faro_no_se_atribuye_pathlib(resolver):
    """El defecto que funda esta spec: Faro decía que Path.cwd era suyo.
    pathlib.Path solo está importado en faro.fuentes.local, no definido ahí."""
    version = resolver.listar_versiones("faro")
    assert not isinstance(version, NoEncontrado)

    v = resolver.verificar_simbolos("faro", version[0], ["Path.cwd"])
    assert v[0].existe
    assert v[0].modulo_origen == "pathlib"
    assert v[0].modulo_origen != "faro"


def test_sqlalchemy_marca_los_pocos_simbolos_realmente_ajenos(resolver):
    """Any es de typing, no de sqlalchemy, aunque sqlalchemy lo re-exporte.
    Confirma la medición de la spec: SQLAlchemy es mayormente propia (~1,4%
    ajeno) frente al 71% de Faro."""
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "Any")
    assert isinstance(r, Fragmento)
    assert r.simbolo == "sqlalchemy.orm.Any"
    assert r.modulo_origen == "typing"
```

- [ ] **Step 2: Correr los tests de contrato**

Run: `uv run pytest -m contrato -v`
Expected: PASS — todos, incluidos los 2 nuevos y los ya existentes (que no deben regresionar: `test_faro_se_encuentra_a_si_mismo`, `test_query_get_existe_en_2_0_y_esta_deprecado`, etc.).

- [ ] **Step 3: Commit**

```bash
git add tests/test_contrato.py
git commit -m "$(cat <<'EOF'
test: contrato — Faro no se atribuye pathlib, SQLAlchemy sí es mayormente propia

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Dogfooding final y cierre de la documentación

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: el servidor completo, vía el mismo snippet de dogfooding que usaron las seis correcciones anteriores.
- Produces: nada de código — solo verificación manual y actualización de la documentación del proyecto.

- [ ] **Step 1: Correr la suite completa una vez más (red final)**

Run: `uv run pytest -m "not contrato" -q && uv run pytest -m contrato -q`
Expected: PASS — dos líneas de resumen, cero fallos.

- [ ] **Step 2: Aplicar Faro sobre Faro (dogfooding manual)**

Correr, tal como pide el patrón ya establecido en CLAUDE.md:

```bash
PYTHONIOENCODING=utf-8 uv run python -c "
import sys; sys.path.insert(0,'src')
from faro.fuentes.local import FuenteLocal
from faro.resolver import ResolverDeDocs
from faro.presentacion import formatear_verificaciones
r = ResolverDeDocs(FuenteLocal(python=sys.executable))
print(formatear_verificaciones(r.verificar_simbolos('faro','0.1.0',['Path.cwd','FastMCP.run']), 'faro'))
"
```

Expected: la salida ya NO dice `Path.cwd: existe (faro.fuentes.local.Path.cwd)` a secas. Debe leerse algo como:

```
Path.cwd: existe (faro.fuentes.local.Path.cwd) — definido en pathlib, no en faro
FastMCP.run: existe (faro.servidor.FastMCP.run) — definido en mcp.server.fastmcp.server, no en faro
```

(El origen exacto de `FastMCP` puede variar según cómo declare `__module__` el SDK de `mcp` instalado — lo que importa es que YA NO se atribuye a `faro`. Confirmar el valor real observado antes de escribir nada en CLAUDE.md.)

También correr `buscar_doc` para confirmar la otra herramienta:

```bash
PYTHONIOENCODING=utf-8 uv run python -c "
import sys; sys.path.insert(0,'src')
from faro.fuentes.local import FuenteLocal
from faro.resolver import ResolverDeDocs
from faro.presentacion import formatear
r = ResolverDeDocs(FuenteLocal(python=sys.executable))
print(formatear(r.buscar_doc('faro','0.1.0','Path.cwd')))
"
```

Expected: la primera línea de salida después de la cita debe decir `definido en: pathlib (no en faro 0.1.0)`.

- [ ] **Step 3: Actualizar CLAUDE.md**

Reemplazar toda la sección `## ⏭️ PENDIENTE — arrancá por acá` (desde ese encabezado hasta el final del archivo, que es donde vive hoy toda la sección "símbolos ajenos") por:

```markdown
## Estado actual

v1 implementada y **mejorada más allá del plan original**. Servidor MCP sobre stdio con
tres herramientas. [N] tests (11 de contrato: SQLAlchemy 2.0.36 real + Faro sobre Faro).
```

(Reemplazar `[N]` por el conteo real que reporte `uv run pytest --collect-only -q | tail -1` tras este cambio — no dejar el placeholder.)

Y agregar una fila nueva a la tabla de "Mejoras post-v1", manteniendo el resto de la tabla intacta:

```markdown
| ⬤ Símbolos ajenos | `<hash del commit de Task 8>` | Faro se atribuía símbolos solo importados, no definidos (`pathlib.Path`, `mcp.FastMCP`): 71% del catálogo de Faro, 1,4% del de SQLAlchemy. No se filtran (rompería `pydantic.ValidationError`, definida en `pydantic_core`): se anota el origen real (`modulo_origen`) en cada símbolo, propagado hasta el texto |
```

Actualizar la frase que sigue a la tabla ("Los cuatro últimos tienen spec...") si hace falta para reflejar que ahora también este defecto tiene spec en `docs/superpowers/specs/2026-07-19-faro-simbolos-ajenos-design.md`.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: cerrar el defecto de símbolos ajenos — Faro sobre Faro confirma el arreglo

Dogfooding manual: Path.cwd y FastMCP.run ya no se citan como propios de
faro. La cita dice explícitamente de dónde vienen de verdad.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review (completado al escribir este plan)

**Cobertura de la spec:** cada sección de `docs/superpowers/specs/2026-07-19-faro-simbolos-ajenos-design.md` tiene tarea — extractor (Task 1), dominio (Task 2), fake/local/resolver (Tasks 3-5), presentación (Task 6), testing de contrato (Task 7), dogfooding (Task 8, pedido explícito del usuario).

**Placeholders:** ninguno — el único valor no fijado de antemano es el hash de commit de Task 8 en la tabla de CLAUDE.md (Step 3) y el conteo de tests, ambos explícitamente marcados como "completar con el valor real observado", no como contenido pendiente de decidir.

**Consistencia de tipos:** `modulo_origen: str` en `EntradaSimbolo`/`Fragmento` (obligatorio) y `str | None = None` en `Verificacion` (opcional) se mantienen consistentes en todas las tareas. `formatear_verificaciones(vs, libreria)` — la firma nueva se usa igual en Task 6 (implementación) y Task 7 no la llama directamente (usa el resolver), sin discrepancias.
