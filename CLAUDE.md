# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado actual

v1 implementada y **mejorada más allá del plan original**. Servidor MCP sobre stdio con
tres herramientas. 112 tests (13 de contrato: SQLAlchemy 2.0.36 real + Faro sobre Faro).

**Comandos:**

```bash
uv sync                          # instalar
uv run pytest -m "not contrato"  # ciclo rápido de TDD (núcleo, sin red)
uv run pytest -m contrato        # tests contra SQLAlchemy 2.0.36 real
uv run pytest tests/test_resolver_buscar.py::test_resuelve_por_sufijo -v   # un solo test
uv run python -m faro.servidor   # arrancar el servidor
```

**Entorno objetivo:** `FARO_PYTHON` apunta al intérprete del proyecto del usuario.
Sin esa variable, Faro lee su propio entorno y lo advierte en cada respuesta.
Ojo: `FARO_PYTHON=""` (vacío) se trata igual que no configurado — `.mcp.json` inyecta
la variable siempre, y sin ese cuidado el fallback prometido no se dispararía.

**La regla de oro al tocar este código:** el núcleo (`resolver.py`, `dominio.py`,
`parseo.py`, `catalogo.py`) **no importa `subprocess`, ni `httpx`, ni `mcp`**. Si un
test del núcleo necesita red o subprocesos, el diseño se rompió.

## Mejoras post-v1 (2026-07-18)

Cerrado el plan de 11 tareas, se hicieron seis cambios. Cuatro de ellos (marcados ⬤) son
**la misma enfermedad**: Faro tenía el dato disponible y no lo mostraba, dando una
respuesta falsamente tranquilizadora.

| Qué | Commit | Detalle |
|---|---|---|
| ⬤ classmethods/staticmethods | `4ae1289` | El extractor solo miraba `inspect.isfunction`/`property`; `URL.create` (constructor canónico) daba "no existe" |
| Re-exports duplicados | `5fb3b55` | `sqlalchemy.Connection` **es** `sqlalchemy.engine.Connection`; contarlos dos veces hacía que `Connection.execute` saliera "ambiguo" por error (variante: no es dato oculto, es el mismo símbolo contado dos veces) |
| ⬤ Métodos heredados | `863af26` | El extractor no caminaba el `__mro__`; `CursorResult.fetchall` daba "no existe" (21 de 47 métodos invisibles en esa clase) |
| ⬤ Firmas de función | `5663f87` | `inspect.signature()` estaba disponible y se descartaba; ahora `buscar_doc` y `verificar_simbolos` la muestran, sin `self`/`cls`. (Mejora, no defecto — pero el mismo patrón: el dato estaba ahí.) |
| ⬤ Deprecaciones en ambigüedad | `cb95ca9` | Una consulta ambigua descartaba TODA la info de deprecación: `get` decía solo "existe" callando que 2 de 8 candidatos son legacy |
| Catálogo automático | `6249ca9` | Amplía alcance, no arregla un defecto: funciona con **cualquier librería instalada**, no solo SQLAlchemy (ver sección propia abajo) |
| ⬤ Símbolos ajenos | `aa5af95` | Faro se atribuía símbolos solo importados, no definidos (`pathlib.Path`, `mcp.FastMCP`): 71% del catálogo de Faro, 1,4% del de SQLAlchemy. No se filtran (rompería `pydantic.ValidationError`, definida en `pydantic_core`): se anota el origen real (`modulo_origen`) en cada símbolo, propagado hasta el texto |

Los cuatro del medio tienen spec en `docs/superpowers/specs/2026-07-18-*`; el último
(símbolos ajenos) tiene la suya en `docs/superpowers/specs/2026-07-19-faro-simbolos-ajenos-design.md`.
Los dos primeros de la tabla no tienen spec: salieron de la revisión final del branch y
de una sesión de dogfooding, y se arreglaron en el momento.

**El patrón que los encontró todos: dogfooding.** Ninguno lo encontraron los tests —
salieron de arrancar el servidor real y preguntarle por su propia dependencia, y de
simular casos de uso concretos. Si vas a tocar Faro, **usalo contra sí mismo antes y
después**; es el método que más defectos reales produjo en este proyecto:

```bash
PYTHONIOENCODING=utf-8 uv run python -c "
import sys; sys.path.insert(0,'src')
from faro.fuentes.local import FuenteLocal
from faro.resolver import ResolverDeDocs
from faro.presentacion import formatear
r = ResolverDeDocs(FuenteLocal(python=sys.executable))
print(formatear(r.buscar_doc('sqlalchemy','2.0.36','Session.execute')))
"
```

(El `PYTHONIOENCODING=utf-8` hace falta en Windows: la consola es cp1252 y el `⚠` de los
avisos de deprecación la revienta.)

## Qué es Faro (definición final, no la del README)

Un servidor MCP que **lee los docstrings del paquete de Python realmente instalado en el venv del
proyecto del usuario** y responde con la versión exacta, el símbolo cualificado, su firma, y
cualquier aviso de deprecación que la propia librería declare. No busca en la web. No tiene caché.
El artefacto instalado es la fuente de verdad.

Librería de referencia: **SQLAlchemy 2.x** (`2.0.36` verificada localmente, y es contra la que
corren los tests de contrato). Pero desde `6249ca9` funciona con **cualquier librería instalada**
— ver "Catálogo automático" abajo.

## Las cinco decisiones cerradas, y por qué (esto YA NO es material de brainstorming)

1. **Construir, no instalar un MCP de terceros.** Motivo del usuario: aprender el protocolo MCP +
   tener control real de fuentes/versiones. Ver sección "Cómo se complementa con Context7" abajo.
2. **Python + `uv`**, no TypeScript. Verificado con la doc oficial de MCP: ambos SDK son **Tier 1**,
   así que "Node va primero en el ecosistema MCP" no es un desempate real. Ganó Python porque (a)
   menos ceremonia de tooling que TypeScript+Zod+tsconfig, y sobre todo (b) **es el único que permite
   introspeccionar un paquete Python en proceso** — esto resultó ser la razón decisiva, ver punto 4.
3. **SQLAlchemy 2.x** como librería objetivo, no FastAPI ni `node:sqlite` ni la API de Claude. Motivo:
   es la única candidata donde el anclaje de versión es *comprobable* — 1.4/2.0/2.1 tienen APIs
   distintas y hay dolor real de InvestSim. *(Sigue siendo la librería de referencia y la que
   cubren los tests de contrato, pero ya no es la única soportada: ver "Catálogo automático".)*
4. **Fuente = paquete instalado (introspección), no la web.** Este cambió respecto al diseño original
   del README (que asumía scraping de `docs.sqlalchemy.org` + su `objects.inv`). Se descartó tras
   comparar con datos reales: el paquete instalado da versión **exacta** (`2.0.36` vs. `2.0`),
   **avisos de deprecación gratis** (la directiva Sphinx `.. deprecated::` vive en el docstring), y
   **no depende de red ni de que el sitio no cambie su HTML**. Se pierde la prosa/tutoriales y las
   versiones no instaladas — aceptado como no-objetivo explícito de v1.
5. **Sin caché.** El venv del usuario *es* la caché: el paquete instalado no cambia bajo los pies.

## El error que fundó el caso de prueba central

Durante el brainstorming, se afirmó **de memoria, con total confianza**, que `sqlalchemy.orm.Query.get`
no existía en SQLAlchemy 2.0. Al verificar contra el paquete real, **sí existe** — documentado como
legacy, con `.. deprecated:: 2.0 ... available as Session.get` en el docstring.

Es exactamente la patología que Faro existe para prevenir, cometida en vivo durante el diseño de la
herramienta que la previene. Por eso:

- El test de contrato central del plan (`test_query_get_existe_en_2_0_y_esta_deprecado`, Task 10) es
  literalmente este caso.
- El parseo de deprecaciones (Task 2) existe como feature de primera clase, no como añadido.
- Si al implementar algo "parece que un símbolo ya no existe en la nueva versión", **verificar contra
  el paquete real antes de asumirlo** — puede estar deprecado, no ausente.

**Y resultó no ser un incidente aislado: es el modo de fallo recurrente del proyecto.** Los
arreglos post-v1 son variantes de lo mismo — Faro afirmando "no existe" sobre API real
(`URL.create`, `CursorResult.fetchall`), o diciendo "existe" a secas sobre API deprecada. Regla
práctica al tocar el extractor o el resolver: **una respuesta que tranquiliza es más sospechosa que
una que alarma.** El falso negativo silencioso es el enemigo, no el falso positivo ruidoso.

## El giro central de diseño: `version` es una afirmación, no una petición

`buscar_doc` y `verificar_simbolos` exigen `version` sin default (regla nº1 de la spec). Pero el
resolver no lo trata como "traeme la doc de esta versión": lo trata como **una afirmación del
consumidor que se verifica contra la realidad del entorno**. Si el asistente asume 1.4 y el venv
tiene 2.0.36, Faro responde que no — nunca sirve la 2.0.36 disfrazada de respuesta a "1.4". Este
mecanismo es `_guarda_de_version` / `version_compatible` en el plan (Task 5) y es, en la práctica,
una trampa para detectar cuándo el modelo está adivinando la versión en vez de saberla.

## Cómo se complementa con Context7 (y por qué no compite)

Se investigó Context7 (MCP de docs de terceros) como parte del brainstorming. Su parámetro de versión
es **opcional** y "matchea automáticamente" — trade-off consciente para cubrir miles de librerías vía
crawling, incompatible con las tres reglas de Faro. No se descartó construir Faro por esto; al
contrario, motivó la tercera herramienta: **`verificar_simbolos`** contrasta cualquier afirmación
sobre la API —de Context7, de un blog, o de la memoria del propio modelo— contra el paquete instalado.
Faro no compite en cobertura (pierde); compite en certeza (ahí gana, porque es el único que mira el
venv real).

## Catálogo automático: cómo Faro sabe qué módulos escanear

Diseño **híbrido** (`6249ca9`):

- **SQLAlchemy tiene una entrada curada** en `catalogo.py` (11 módulos elegidos a mano). Gana
  siempre que exista: evita el ruido de dialectos internos, utilidades de testing, etc.
- **Cualquier otra librería se descubre sola.** `local.py` manda `modulos: null` al extractor, y
  `extractor.py` camina los submódulos públicos con `pkgutil.walk_packages` (excluye cualquiera
  con un `_` inicial en algún segmento).

**Por qué el descubrimiento vive en `extractor.py` y no en `local.py`:** `local.py` corre en el
proceso de Faro, que **no tiene instalada** la librería del proyecto objetivo — no puede importarla
para inspeccionar su `__path__`. Solo el subproceso puede. Si vas a tocar esto, ese es el motivo.

**Consecuencia de diseño ya aplicada:** se eliminó el gate de catálogo del resolver
(`_verificar_catalogo`). Ya no existe una "lista cerrada de librerías conocidas", así que el único
camino de fallo es el honesto: *"'X' no está instalada en el entorno objetivo."* `ResolverDeDocs`
ya no recibe un parámetro `catalogo`, y `catalogo.py` hoy solo lo consume `local.py`.

## Arquitectura (ya no tentativa — ver la spec para el diagrama completo)

Dependency Rule. El núcleo (`resolver.py`, `dominio.py`, `parseo.py`, `catalogo.py`) **no importa
`subprocess`, `httpx` ni `mcp`**. Habla con el puerto `FuenteDeDocs` (`Protocol`). Producción usa
`FuenteLocal`, que lanza un **subproceso** con el intérprete del proyecto objetivo (`FARO_PYTHON`)
ejecutando `extractor.py` — un script aparte que solo usa stdlib, porque corre dentro de un venv
ajeno y porque importar un paquete ejecuta su código de módulo (no debe pasar dentro del proceso de
Faro). Tests usan `FuenteFake` con datos reales de SQLAlchemy 2.0.36 congelados como fixtures.

Regla dura para cualquier cambio futuro: **si un test del núcleo necesita red o subprocesos, el
diseño se rompió.**

**`FuenteFake` discrimina por librería.** Antes devolvía la misma versión para cualquier nombre;
funcionaba solo porque el gate de catálogo interceptaba lo desconocido antes de llegar a ella. Sin
ese gate, la fake tiene que distinguir sola su librería (`libreria="sqlalchemy"` por defecto) —
si agregás tests con otras librerías, pasale el parámetro.

## graphify

Grafo generado y funcionando: `graphify-out/graph.json` (201 nodos, 333 edges sobre 27 archivos
de código). Hay un `.graphifyignore` propio en la raíz, copiado del patrón de los proyectos
hermanos (excluye `*.json`, `*.md`, `*.lock` — sin eso, cada clave de un archivo de config se
vuelve un nodo y ahoga la señal real).

`graphify-out/` está en `.gitignore`: no se comitea, así que su ausencia tras un `git pull` /
`checkout` es normal. Regenerarlo con:

```bash
graphify extract . --code-only
```

**No correr `graphify install --project`.** Se probó y hace dos cosas no deseadas: instala hooks
en `.claude/` (que ningún proyecto hermano tiene) y **sobrescribe esta sección del CLAUDE.md con
texto genérico en inglés**, rompiendo la convención de "todo en español". Se revirtió.

## No-objetivos explícitos (no proponer estas features sin pasar por brainstorming)

- Nada de búsqueda en prosa/tutoriales/guías de migración — solo referencia de API.
- Nada de versiones no instaladas — Faro puede sugerir instalarlas, nunca inventa su contenido.
- Nada de librerías no-Python (`node:sqlite` queda fuera por construcción).
- No juzga idiomaticidad más allá de lo que la librería declara con `.. deprecated::`.
- **Nada de inferencia de tipos.** Decisión explícita: sería escribir un mini type-checker, y crea
  un lugar nuevo donde Faro podría inferir mal y afirmar algo falso con confianza — justo lo que
  el proyecto existe para evitar.

*(Ya no son no-objetivos: métodos heredados, firmas de función y librerías fuera del catálogo —
los tres se implementaron. Si el README o un spec viejo dice lo contrario, está desactualizado.)*

## `verificar_codigo`: diseñado, evaluado y **puesto en pausa a propósito**

Se diseñó una cuarta herramienta que recibiría un bloque de código y auditaría sus llamadas contra
el paquete instalado. **No se construyó, y la decisión fue deliberada** — no la retomes sin leer
esto:

1. **Falla el caso fundacional.** Sin inferencia de tipos (que es no-objetivo, ver arriba),
   `session.query(User).get(5)` produce las consultas `query` y `get` — ambas ambiguas. Antes del
   fix `cb95ca9` eso respondía "existe" a secas, callando la deprecación de `Query.get`: la
   herramienta habría fallado exactamente en el caso que le da sentido al proyecto.
2. **Descarta información que quien llama ya tiene.** Un asistente leyendo
   `session.query(User).get(5)` ya sabe que eso es `Query.get`, y puede preguntar por el nombre
   calificado — obteniendo una respuesta precisa con su deprecación, en vez de "ambiguo entre 8".
   El análisis AST sin tipos *pierde* precisión respecto de preguntar bien.
3. **No cierra el agujero que la motivaba.** El modo de fallo que Faro combate es el asistente que
   está seguro y por eso *no pregunta*. Una herramienta que hay que invocar a mano tiene el mismo
   agujero. Eso lo cierra un hook o una regla de workflow, no la existencia de la herramienta.

**Si se retoma, el orden correcto es: primero el disparador automático, después la herramienta.**

Nota valiosa: el ejercicio de diseñarla no se desperdició — simular su comportamiento sobre el caso
fundacional fue lo que destapó el defecto de deprecaciones-en-ambigüedad (`cb95ca9`), que ya estaba
en producción.

## Convenciones

- **Todo en español**: código, nombres de herramientas MCP (`buscar_doc`, `listar_versiones`,
  `verificar_simbolos`), mensajes al usuario, commits.
- Python `>=3.12`, gestionado con `uv` (no `pip`/`venv` a mano).
- Commits en español, formato imperativo, con `Co-Authored-By` cuando los genera Claude.
