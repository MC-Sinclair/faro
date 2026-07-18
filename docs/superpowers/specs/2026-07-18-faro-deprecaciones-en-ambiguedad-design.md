# Faro — deprecaciones visibles en la ambigüedad (design)

## Contexto y motivación

Cuando una consulta resuelve a varios símbolos, Faro descarta toda la información
de deprecación de los candidatos. Verificado contra SQLAlchemy 2.0.36 real:

```
>>> verificar_simbolos("sqlalchemy", "2.0.36", ["get"])
get: existe (ambiguo: varios símbolos coinciden)

>>> buscar_doc("sqlalchemy", "2.0.36", "get")
AMBIGUO: 'get' resuelve a varios símbolos. Pedí uno concreto:
  - sqlalchemy.engine.RowMapping.get
  - sqlalchemy.ext.asyncio.AsyncSession.get
  - sqlalchemy.ext.asyncio.async_scoped_session.get
  - sqlalchemy.orm.AppenderQuery.get
  - sqlalchemy.orm.Query.get
  - sqlalchemy.orm.Session.get
  - sqlalchemy.orm.scoped_session.get
  - sqlalchemy.sql.expression.ColumnCollection.get
```

Pero Faro **tiene** el dato y lo tira:

```
get: 8 candidatos, 2 deprecados
    DEPRECADO: sqlalchemy.orm.AppenderQuery.get -> Session.get
    DEPRECADO: sqlalchemy.orm.Query.get         -> Session.get
```

Dos consecuencias, ambas malas:

1. `verificar_simbolos` responde "existe" — que se lee como tranquilizador —
   mientras calla que 2 de las 8 coincidencias son API legacy.
2. `buscar_doc` es hasta peor: te pide elegir entre 8 opciones y presenta las 2
   deprecadas como pares iguales de las vigentes, sin marca alguna.

Es la misma enfermedad que ya se corrigió tres veces en este proyecto
(`Query.get` original, re-exports, herencia): Faro tiene la información, no la
muestra, y da una respuesta falsamente tranquilizadora.

**Cómo se encontró:** simulando qué respondería una futura herramienta de
auditoría de bloques de código (`verificar_codigo`) sobre el caso fundacional
del proyecto, `session.query(User).get(5)`. Sin inferencia de tipos, ese código
produce las consultas `query` y `get` — y Faro respondía "existe (ambiguo)" a
ambas, fallando exactamente en el caso que le da sentido al proyecto. El defecto
resultó ser preexistente y estar en producción, no en el diseño nuevo.

## Decisiones (cerradas con el usuario)

1. **En `verificar_simbolos`: solo los deprecados, nombrándolos** — no se
   vuelca la lista completa de candidatos (ahí no se muestra la lista).
2. **En `buscar_doc`: marcar en línea** — la lista completa ya se muestra por
   diseño (es la función de `Ambiguo`: dar las opciones para elegir), así que
   marcar los deprecados ahí no agrega longitud, y omitirlo sería presentar
   trampas como opciones válidas.

## Diseño

### Dominio (`src/faro/dominio.py`)

Nuevo dataclass:

```python
@dataclass(frozen=True)
class CandidatoDeprecado:
    """Un candidato de una consulta ambigua que además está deprecado."""

    nombre: str
    deprecacion: Deprecacion
```

Nuevo campo en `Ambiguo` y `Verificacion` (requiere `field` de `dataclasses`):

```python
@dataclass(frozen=True)
class Ambiguo:
    consulta: str
    candidatos: list[str]
    deprecados: list[CandidatoDeprecado] = field(default_factory=list)

@dataclass(frozen=True)
class Verificacion:
    simbolo: str
    existe: bool
    resuelto_como: str | None
    deprecacion: Deprecacion | None
    firma: str | None = None
    deprecados: list[CandidatoDeprecado] = field(default_factory=list)
```

`Ambiguo.candidatos` y `Verificacion.deprecacion` **no** cambian — nada
existente se rompe.

**Por qué `deprecacion` (singular) y `deprecados` (plural) coexisten:** son
situaciones distintas. `deprecacion` es "el símbolo que pediste, resuelto sin
ambigüedad, está deprecado". `deprecados` es "algunas de las varias cosas que tu
consulta podría significar lo están". Colapsarlas en un campo obligaría a elegir
un reemplazo cuando puede haber varios distintos — justo lo que Faro no hace.

### Núcleo (`src/faro/resolver.py`)

Helper nuevo a nivel de módulo:

```python
def _deprecados_de(entradas: list[EntradaSimbolo]) -> list[CandidatoDeprecado]:
    return [
        CandidatoDeprecado(nombre=e.nombre, deprecacion=e.deprecacion)
        for e in sorted(entradas, key=lambda e: e.nombre)
        if e.deprecacion is not None
    ]
```

Usado en las dos ramas ambiguas:

- `buscar_doc`: `Ambiguo(consulta=..., candidatos=..., deprecados=_deprecados_de(candidatos))`
- `verificar_simbolos` (rama `len(candidatos) > 1`): idem en el `Verificacion`.

Cero lógica nueva de resolución: `_candidatos` no cambia.

### Presentación (`src/faro/presentacion.py`)

`formatear()`, rama `Ambiguo` — marcar en línea:

```
AMBIGUO: 'get' resuelve a varios símbolos. Pedí uno concreto:
  - sqlalchemy.engine.RowMapping.get
  - sqlalchemy.orm.AppenderQuery.get  ⚠ DEPRECADO desde 2.0 — usar Session.get
  - sqlalchemy.orm.Query.get  ⚠ DEPRECADO desde 2.0 — usar Session.get
  - sqlalchemy.orm.Session.get
```

El aviso reusa el mismo formato que ya usa la rama `Fragmento` (`⚠ DEPRECADO
desde X — usar Y`), y el `— usar Y` solo aparece si hay reemplazo declarado.

`formatear_verificaciones()`, rama ambigua — cada deprecado con **su propio**
reemplazo (pueden diferir):

```
get: existe (ambiguo: varios símbolos coinciden) — ⚠ 2 candidatos DEPRECADOS: sqlalchemy.orm.AppenderQuery.get (usar Session.get), sqlalchemy.orm.Query.get (usar Session.get)
```

Si un candidato deprecado no declara reemplazo, se lista solo su nombre, sin el
paréntesis.

Si `deprecados` está vacío (el caso normal), ninguna de las dos salidas cambia
en nada respecto de hoy.

## Testing

**Fixture: no hace falta tocarlo.** `simbolos_de_prueba()`
(`src/faro/fuentes/fake.py`) ya contiene `sqlalchemy.orm.Session.get` y
`sqlalchemy.orm.Query.get`, así que la consulta `get` da 2 candidatos con
exactamente 1 deprecado — el caso exacto que hay que probar, con datos reales.

**Resolver (`tests/test_resolver_buscar.py`, `tests/test_resolver_verificar.py`):**
- `buscar_doc("get")` devuelve `Ambiguo` cuyo `deprecados` contiene `Query.get`
  con su reemplazo `Session.get`, y NO contiene `Session.get` (que no está
  deprecado).
- `verificar_simbolos(["get"])` devuelve una `Verificacion` ambigua
  (`resuelto_como is None`) cuyo `deprecados` contiene `Query.get`.
- Una consulta ambigua sin deprecados (`select`, ya en el fixture) devuelve
  `deprecados == []`.

**Presentación (`tests/test_presentacion.py`):**
- `Ambiguo` con `deprecados` muestra la marca en línea junto al candidato
  correcto, y no junto a los demás.
- `Verificacion` ambigua con `deprecados` muestra el resumen con nombres y
  reemplazos.
- Ambos casos con `deprecados=[]` producen exactamente la misma salida que hoy
  (protege contra cambios de forma no intencionados).

**Contrato, SQLAlchemy real (`tests/test_contrato.py`):**
- `buscar_doc("get")` sobre SQLAlchemy real da `Ambiguo` con al menos
  `sqlalchemy.orm.Query.get` entre los `deprecados`, con reemplazo
  `Session.get` — el caso de 8 candidatos / 2 deprecados verificado arriba.

## Fuera de alcance (explícito)

- No se construye `verificar_codigo` (auditoría de bloques de código). Este
  arreglo es prerrequisito de esa idea, pero la idea queda en pausa hasta tener
  claro qué la dispararía automáticamente — una herramienta que hay que invocar
  a mano no cierra el agujero que la motivaba (el asistente que está seguro y
  por eso no pregunta).
- No se cambia `_candidatos` ni la regla de resolución exacto/sufijo.
- No se agrega inferencia de tipos en ningún lado.
