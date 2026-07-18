# Faro — firmas de función (design)

## Contexto y motivación

Hoy Faro devuelve el docstring de un símbolo pero no su firma (qué parámetros
acepta, cuáles son opcionales, qué devuelve). Para un asistente, "¿cómo se llama
esto exactamente?" es al menos tan frecuente como "¿qué hace?" — y es información
que `inspect.signature()` ya puede dar gratis sobre el paquete instalado, en línea
con el resto de la filosofía de Faro (mirar el código real, no aproximar).

Es además una segunda capa de prevención de alucinación: `verificar_simbolos` hoy
puede confirmar que un método existe, pero no si los argumentos que el asistente
está por usar son los correctos.

## Decisiones (ya cerradas con el usuario)

1. **Se saca `self`/`cls` de la firma mostrada.** Para classmethods, Python ya lo
   hace solo al resolver el descriptor vía `getattr`. Para métodos de instancia,
   se saca a mano cuando el primer parámetro se llama `self` (heurística segura:
   es la convención universal de Python, no una interpretación arriesgada).
2. **La firma aparece en las dos herramientas**, `buscar_doc` y `verificar_simbolos`
   — no solo en la primera.

## Diseño

### Extractor (`src/faro/fuentes/extractor.py`)

Nueva función `_firma_de(objeto) -> str | None`:

```python
def _firma_de(objeto: object) -> str | None:
    try:
        firma = inspect.signature(objeto)
    except (ValueError, TypeError):
        return None
    parametros = list(firma.parameters.values())
    if parametros and parametros[0].name in ("self", "cls"):
        firma = firma.replace(parameters=parametros[1:])
    return str(firma)
```

`_anotar()` pasa a guardar `{"doc": ..., "firma": ...}` en vez de solo el string de
doc, y recibe un segundo objeto opcional sobre el cual calcular la firma (porque el
objeto usado para `inspect.getdoc()` — el descriptor crudo de `vars(clase)`, que ya
funciona bien para distinguir classmethod/staticmethod/property — NO es el mismo
objeto sobre el que hay que calcular la firma; para eso hace falta la versión
*resuelta* vía `getattr(base, nombre_attr)`, que es la que ya excluye `cls` para
classmethods):

```python
def _anotar(vistos, nombre, objeto_doc, objeto_firma=None) -> None:
    if nombre in vistos:
        return
    try:
        doc = inspect.getdoc(objeto_doc)
    except Exception:
        return
    if not doc:
        return
    vistos[nombre] = {
        "doc": doc,
        "firma": _firma_de(objeto_firma if objeto_firma is not None else objeto_doc),
    }
```

En `_anotar_miembros` (la función que ya camina el `__mro__`, del fix de herencia),
cada llamada a `_anotar` pasa también `getattr(base, nombre_attr)` como
`objeto_firma`. En las llamadas para clases y funciones de nivel de módulo, no hace
falta el segundo argumento: `inspect.signature(Clase)` ya da la firma del
constructor sin necesidad de resolver nada aparte.

`extraer()` cambia su salida final:

```python
return [
    {"nombre": n, "doc": v["doc"], "firma": v["firma"]}
    for n, v in sorted(vistos.items())
]
```

### Modelo de dominio (`src/faro/dominio.py`)

Nuevo campo, con default para no forzar a tocar cada fixture existente:

```python
@dataclass(frozen=True)
class EntradaSimbolo:
    nombre: str
    doc: str
    deprecacion: Deprecacion | None
    firma: str | None = None

@dataclass(frozen=True)
class Fragmento:
    libreria: str
    version: str
    simbolo: str
    texto: str
    deprecacion: Deprecacion | None
    firma: str | None = None

@dataclass(frozen=True)
class Verificacion:
    simbolo: str
    existe: bool
    resuelto_como: str | None
    deprecacion: Deprecacion | None
    firma: str | None = None
```

### Adaptador (`src/faro/fuentes/local.py`)

`simbolos()` lee la nueva clave del JSON crudo:

```python
EntradaSimbolo(
    nombre=s["nombre"],
    doc=s["doc"],
    firma=s.get("firma"),
    deprecacion=extraer_deprecacion(s["doc"]),
)
```

### Núcleo (`src/faro/resolver.py`)

`buscar_doc` copia `firma=entrada.firma` al construir `Fragmento`.
`verificar_simbolos` copia `firma=e.firma` en el caso "existe, resuelto sin
ambigüedad" — en los casos "no existe" y "ambiguo" no hay entrada de la que sacar
una firma, así que queda en `None` (el default).

### Presentación (`src/faro/presentacion.py`)

`formatear()`: si `r.firma` no es `None`, se agrega una línea con la firma,
inmediatamente después de la cita (y del aviso de deprecación, si lo hay), antes
de la línea en blanco que separa el docstring:

```
sqlalchemy 2.0.36 :: sqlalchemy.orm.Session.execute
execute(statement, parameters=None, *, execution_options=None, bind_arguments=None) -> Result[Any]

Execute a SQL expression construct.
```

`formatear_verificaciones()`: si `v.firma` no es `None`, se agrega al final de la
línea existente:

```
Session.execute: existe (sqlalchemy.orm.Session.execute) — execute(statement, parameters=None, ...)
```

Si `firma` es `None` (no se pudo calcular, o el símbolo no existe/es ambiguo), no
se agrega nada — ni línea vacía ni placeholder tipo "sin firma".

## Testing

**Extractor, sin red (`tests/test_extractor.py`):**
- Firma de una función simple de la stdlib se captura correctamente.
- `pathlib.Path.cwd` (classmethod, fixture ya usada por el fix de re-exports) da
  una firma sin `cls`.
- Un método de instancia da una firma sin `self`.
- Una property no rompe la extracción y da `firma=None` para esa entrada (el doc
  sigue extrayéndose igual).

**Presentación (`tests/test_presentacion.py`):**
- Un `Fragmento` con `firma` fijada aparece en la salida de `formatear()`.
- Un `Fragmento` con `firma=None` (el caso ya cubierto por los tests existentes,
  que no la fijan) no agrega ninguna línea de más — se verifica que el output no
  cambia de forma para el caso sin firma.
- `formatear_verificaciones()` con y sin firma, análogo.

**Contrato, SQLAlchemy real (`tests/test_contrato.py`):**
- La firma real de `Session.execute` incluye el parámetro `statement`.

**Resolver (`tests/test_resolver_buscar.py` o el fixture de `fake.py`):**
- Se agrega una firma real a la entrada `sqlalchemy.orm.Session.execute` en
  `simbolos_de_prueba()` (`src/faro/fuentes/fake.py`), y un test verifica que
  `resolver.buscar_doc(...).firma` llega con ese valor — prueba el cableado
  completo extractor→dominio→resolver sin necesitar red (vía `FuenteFake`).

## Fuera de alcance (explícito)

- No se limpian los tipos con comillas que aparecen en firmas de librerías que
  usan anotaciones diferidas (`statement: 'Executable'` en vez de `Executable`) —
  es el string real que Python devuelve, mostrarlo tal cual es consistente con
  "no interpretar, solo relayar lo real".
- No se toca el catálogo automático de librerías — es la tercera mejora de la
  lista, con su propio diseño.
