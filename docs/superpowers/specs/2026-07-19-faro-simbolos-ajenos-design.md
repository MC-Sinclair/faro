# Símbolos ajenos atribuidos a la librería — diseño

**Fecha:** 2026-07-19
**Estado:** aprobado, pendiente de plan de implementación

## El defecto

Faro atribuye a una librería símbolos que no son suyos, sino solo importados en
alguno de sus módulos. Reproducción exacta (ya verificada, no repetir):

```bash
PYTHONIOENCODING=utf-8 uv run python -c "
import sys; sys.path.insert(0,'src')
from faro.fuentes.local import FuenteLocal
from faro.resolver import ResolverDeDocs
from faro.presentacion import formatear_verificaciones
r = ResolverDeDocs(FuenteLocal(python=sys.executable))
print(formatear_verificaciones(r.verificar_simbolos('faro','0.1.0',['Path.cwd','FastMCP.run'])))
"
```

Devuelve `Path.cwd: existe (faro.fuentes.local.Path.cwd)` — pero `Path` es
`pathlib.Path` (stdlib), no de Faro. La cita `faro 0.1.0 :: Path.cwd` es
sencillamente falsa: la versión de Faro no dice nada sobre `pathlib`.

**Causa:** `extraer()` en `extractor.py` recorre `vars(modulo)` y toma toda
clase o función pública, sin distinguir si el objeto fue *definido* en esa
librería o solo *importado* ahí.

**Medición ya hecha:**

| Librería | Símbolos ajenos |
|---|---|
| SQLAlchemy | 7 de 498 (1,4%) — todos de `typing`/`typing_extensions` |
| Faro | 92 de 129 (71%) — `pathlib.Path` + `mcp.FastMCP` |

Es la imagen espejo de los seis defectos ya corregidos: esos eran falsos
negativos (Faro negando API real); este es un falso positivo (Faro
afirmando API que no es de la librería).

## Decisión de diseño: atribuir, no filtrar

La corrección propuesta originalmente (ver sección legada de CLAUDE.md) era
filtrar — no registrar el símbolo si es ajeno. **Se descarta.** Medido contra
`pydantic` real (instalada en este entorno):

```
pydantic: 97 propios, 7 ajenos
    ValidationError      <- pydantic_core
    ValidationInfo        <- pydantic_core
    SerializationInfo     <- pydantic_core
    ...
```

`pydantic.ValidationError` es API pública documentada de pydantic; que esté
*definida* en `pydantic_core` (el núcleo compilado en Rust) es un detalle de
implementación. Filtrarla haría que Faro respondiera "no existe" — un falso
negativo silencioso, exactamente la enfermedad que las seis correcciones
anteriores curaron. Un filtro sería la única de las siete correcciones que
*quita* información en vez de agregarla.

**La solución es mostrar el origen, no ocultar el símbolo.** El problema
nunca fue que el símbolo aparezca: fue la cita falsa de versión/librería.
Se resuelve diciendo la verdad (`definido en pathlib, no en faro`), no
mintiendo por omisión (dejar de mencionarlo).

## Arquitectura

Un dato nuevo, `modulo_origen`, viaja por el pipeline existente sin tocar la
Dependency Rule. Se calcula en `extractor.py` —el único lugar con el objeto
vivo y su `__module__`— cruza como campo del JSON de salida, y aterriza en
`EntradaSimbolo` → `Fragmento`/`Verificacion` → texto. `resolver.py` no
necesita lógica nueva: solo propaga el campo, igual que ya hace con `firma`.

`extraer()` gana un parámetro `libreria: str` (hoy solo recibe `modulos`) para
tener contra qué comparar el origen de cada símbolo. `main()` ya conoce
`libreria` desde la petición, así que el cambio es mecánico.

## Componentes y flujo de datos

### `extractor.py`

- **`_raiz_modulo(objeto, libreria) -> str`** (nueva función):
  ```python
  def _raiz_modulo(objeto: object, libreria: str) -> str:
      origen = (getattr(objeto, "__module__", "") or "").split(".")[0]
      return origen or libreria
  ```
  El `or libreria` es el fallback deliberado para extensiones C o builtins sin
  `__module__`: sin evidencia de lo contrario, se asume propio. No es un
  descuido, es la decisión conservadora — no introducir un falso "ajeno" por
  falta de dato, igual que antes de este cambio.

- **`extraer(libreria: str, modulos: list[str])`**: gana el parámetro
  `libreria`. Para cada clase/función top-level halladas en `vars(modulo)`,
  se calcula `origen = _raiz_modulo(objeto, libreria)` y se pasa a `_anotar`
  y a `_anotar_miembros`.

- **`_anotar_miembros(vistos, nombre_clase, clase, origen_clase)`**: gana el
  parámetro `origen_clase`, calculado una sola vez por el caller para la
  clase dueña. Todo método heredado por `__mro__` hereda ESE origen, no el
  `__module__` de la base específica donde el método vive físicamente.

  Esto es una decisión explícita: `Path.cwd` es ajeno porque `Path` lo es
  (toda la clase es de `pathlib`). Un hipotético `MiClase(dict)` propio de
  una librería tendría `MiClase.keys` como **propio** — heredado de `dict`,
  pero expuesto como parte de la superficie de `MiClase` desde el punto de
  vista de quien la usa. Un solo mecanismo cubre ambos casos sin lógica
  especial adicional, y es coherente con cómo ya se trata la herencia entre
  clases de la MISMA librería (`863af26`).

- **`_anotar(vistos, nombre, objeto_doc, objeto_firma, modulo_origen)`**: gana
  `modulo_origen: str` y lo guarda en el dict de salida junto a `doc`/`firma`.

- **JSON de salida**: cada símbolo suma `"modulo_origen": "..."`.

### `dominio.py`

- `EntradaSimbolo.modulo_origen: str` — siempre presente, no opcional.
- `Fragmento.modulo_origen: str` — siempre presente.
- `Verificacion.modulo_origen: str | None` — `None` cuando `existe=False` o
  cuando es ambiguo (mismo patrón ya establecido para `resuelto_como` y
  `firma`: no se afirma un origen único si la consulta no resolvió a un
  símbolo concreto).

### `local.py`

Un campo más al construir `EntradaSimbolo` desde el JSON crudo del
extractor, igual que ya hace con `firma`.

### `fake.py`

Los `EntradaSimbolo` de `simbolos_de_prueba()` necesitan `modulo_origen` con
el valor real correcto (`"sqlalchemy"` para las entradas existentes, todas
símbolos reales de esa librería) — no un placeholder, para no introducir
falsedad en los datos de prueba que ya presumen ser reales.

### `presentacion.py`

- **`formatear()`** (Fragmento): nueva línea después del encabezado.
  - Propio: `definido en: {libreria} {version}`.
  - Ajeno: `definido en: {modulo_origen} (no en {libreria} {version})`.
  - Se anota siempre, en ambos casos — decisión explícita para no dejar
    ambigüedad sobre si la anotación falta porque es propio o porque se
    omitió.

- **`formatear_verificaciones()`** (Verificacion): el origen se agrega al
  final de la línea SOLO cuando es ajeno y solo cuando `resuelto_como is not
  None` (hay un símbolo concreto resuelto, no un empate ambiguo):
  `... — definido en {modulo_origen}`. Cuando es propio, no se agrega nada.

  Esta es una asimetría deliberada respecto de `formatear()`: el formato de
  `verificar_simbolos` es una línea por símbolo consultado, ya con varios
  sufijos condicionales (deprecación, candidatos deprecados, firma). Anotar
  el caso propio en cada línea saturaría el formato con información
  redundante en el caso común (la mayoría de los símbolos consultados sí son
  propios). El caso ajeno, al ser la excepción, se destaca precisamente por
  aparecer solo cuando aplica.

## Manejo de errores y casos borde

- **`__module__` ausente o vacío**: fallback a `libreria` (tratado como
  propio por falta de evidencia en contra).
- **Métodos heredados de clase ajena**: heredan el origen de la clase dueña,
  calculado una sola vez y propagado a todo el `__mro__`.
- **Re-exports dentro de la misma librería** (`sqlalchemy.Connection` ==
  `sqlalchemy.engine.Connection`): sin cambios — siguen deduplicándose por
  identidad antes de que el origen entre en juego; ambos caminos dan
  `origen = "sqlalchemy"`.
- **Ambigüedad**: `modulo_origen = None` en `Verificacion`, igual que
  `resuelto_como`/`firma`.
- **`NoEncontrado`**: sin cambios, no lleva `modulo_origen`.
- **Compatibilidad de fixtures**: `FuenteFake`/`simbolos_de_prueba()` migran
  con el valor real, no un default arbitrario.

## Testing

- **Extractor** (`test_extractor.py`):
  - símbolo top-level propio → `modulo_origen == libreria`.
  - símbolo top-level ajeno (fixture con un objeto importado de otra
    librería/stdlib) → `modulo_origen` = la librería real de origen.
  - método heredado de base ajena → hereda el origen ajeno de la clase
    dueña, no el `__module__` de la base física.
  - método heredado de base propia (caso `863af26`, ya cubierto) → sigue
    dando `modulo_origen == libreria`; no debe regresionar.
- **Resolver** (`test_resolver_buscar.py`, `test_resolver_verificar.py`):
  `Fragmento`/`Verificacion` propagan `modulo_origen` sin transformarlo;
  ambiguo da `None`.
- **Presentación** (`test_presentacion.py`): las dos líneas de `formatear()`
  (propio vs. ajeno); el sufijo condicional (solo-si-ajeno,
  solo-si-resuelto) de `formatear_verificaciones()`.
- **Contrato** (`test_contrato.py`, `-m contrato`) — casos fundacionales de
  esta spec:
  - `verificar_simbolos('faro', '0.1.0', ['Path.cwd'])` → `existe=True,
    modulo_origen='pathlib'`, y el texto formateado dice explícitamente que
    no es de Faro.
  - Un caso positivo real de SQLAlchemy: `Any` (de `typing`) sale marcado
    ajeno — confirma la medición del 1,4% ya hecha en esta spec.
  - `ResolverDeDocs.buscar_doc` sigue funcionando sin romper ningún caso
    existente (deprecaciones, ambigüedad, herencia, firmas).
- **Dogfooding manual** (patrón que encontró los seis defectos anteriores):
  repetir el snippet de reproducción de esta spec contra Faro mismo,
  antes/después del cambio, y confirmar que la cita ya no es falsa.

## No-objetivos de este cambio

- No se resuelve la versión instalada del módulo de origen ajeno (p. ej. no
  se agrega "pydantic_core 2.20.1", solo "pydantic_core"). Decisión
  explícita: mantiene el arreglo acotado a su propósito —dejar de mentir
  sobre QUIÉN define el símbolo—, sin abrir una segunda resolución de
  versión por cada origen distinto encontrado, con sus propios casos borde.
  Se puede agregar después si hace falta.
- No se decide nada sobre re-exports "declarados como API pública" de forma
  especial (p. ej. un `__all__` explícito). El origen se basa puramente en
  `__module__`; si una librería quiere que Faro trate un re-export como
  propio, la solución de fondo es que esa librería lo defina en su propio
  módulo, no que Faro adivine intención por `__all__`.
