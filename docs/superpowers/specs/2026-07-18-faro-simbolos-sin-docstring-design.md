# Faro — un símbolo existe aunque no esté documentado (design)

## Contexto y motivación

Aplicando Faro sobre Faro (`faro` está instalado en su propio venv, versión `0.1.0`),
el resultado fue:

```
ResolverDeDocs.buscar_doc:       NO EXISTE en esta versión.
ResolverDeDocs.listar_versiones: NO EXISTE en esta versión.
ResolverDeDocs.verificar_simbolos: existe (...)
```

Faro declara inexistentes a **dos de sus propias tres herramientas MCP**.

La correlación resultó exacta: los símbolos con docstring se encuentran, los que no
tienen docstring se reportan como inexistentes. La causa está en `extractor.py`:

```python
def _anotar(...):
    ...
    if not doc:
        return   # el símbolo se descarta ENTERO, no solo su doc
```

El extractor confunde **"no tengo documentación de esto"** con **"esto no existe"**.
Son afirmaciones distintas, y Faro está haciendo la segunda cuando solo sabe la primera.

Es el mismo modo de fallo que el proyecto ya corrigió cinco veces (classmethods,
re-exports, herencia, firmas, deprecaciones-en-ambigüedad) — el sexto caso, y el más
fundamental, porque está en la raíz del extractor y afecta a todo lo que pasa por ahí.

**Por qué es urgente ahora y no antes:** mientras Faro era solo-SQLAlchemy, el punto
ciego era marginal — SQLAlchemy está excepcionalmente bien documentada (`Session` y
`Engine` tienen 100% de cobertura de docstrings). El catálogo automático (`4b2ba6a`)
cambió el cálculo: ahora Faro trabaja con cualquier librería instalada, y va a
encontrarse constantemente con código normal, donde no todo método público tiene
docstring. El caso `faro` no es una anécdota: es representativo de una librería típica.

## El trade-off, medido

Medido sobre SQLAlchemy 2.0.36 real con el catálogo curado:

| | |
|---|---|
| Símbolos hoy negados falsamente | **446** |
| Crecimiento del catálogo al dejar de filtrar | +8% (5448 → 5894) |
| Consultas que pasarían de única a ambigua | **9 de 626** (1,4%) |

Ejemplos de las 9: `count` (1 → 3 candidatos), `append_column`, `bindparams`,
`comparator`, `entity` (1 → 2 cada una).

Relación ~50:1 a favor del arreglo. Y el "costo" no son respuestas incorrectas: Faro
dirá *"hay 3 cosas que se llaman `count`, elegí una"*, que es cierto y accionable. El
comportamiento actual dice *"no existe"* sobre cosas que existen, que es falso. Se
cambia una imprecisión honesta por una afirmación falsa.

## Decisiones (cerradas con el usuario)

1. **`buscar_doc` sobre un símbolo sin doc devuelve `Fragmento` con aviso explícito**
   — no un `NoEncontrado`, y no un fragmento con cuerpo vacío sin explicación. Dice
   toda la verdad: existe, así se llama, y no declara documentación.
2. **`verificar_simbolos` no marca los símbolos sin doc.** Ahí la pregunta es
   "¿existe?" y la respuesta es sí; el estado de su documentación es irrelevante para
   ese veredicto y agregarlo sería ruido en listas largas.

## Diseño

### Extractor (`src/faro/fuentes/extractor.py`)

`_anotar` deja de descartar por falta de doc:

```python
def _anotar(vistos, nombre, objeto_doc, objeto_firma=None) -> None:
    if nombre in vistos:
        return
    try:
        doc = inspect.getdoc(objeto_doc)
    except Exception:
        doc = None
    vistos[nombre] = {
        "doc": doc,
        "firma": _firma_de(objeto_firma if objeto_firma is not None else objeto_doc),
    }
```

Nota: el `except Exception` pasa de `return` (descartar el símbolo) a `doc = None`
(registrarlo sin doc) — misma lógica, por el mismo motivo: que `getdoc` falle no
significa que el símbolo no exista.

El JSON de salida ya emite `doc` tal cual esté; ahora puede ser `null`.

### Dominio (`src/faro/dominio.py`)

```python
@dataclass(frozen=True)
class EntradaSimbolo:
    nombre: str
    doc: str | None          # era str
    deprecacion: Deprecacion | None
    firma: str | None = None

@dataclass(frozen=True)
class Fragmento:
    libreria: str
    version: str
    simbolo: str
    texto: str | None        # era str
    deprecacion: Deprecacion | None
    firma: str | None = None
```

**Regla 2 no se debilita:** la garantía estructural es que un `Fragmento` no pueda
existir sin `libreria`, `version` y `simbolo`. `texto` nunca formó parte de esa
garantía — sigue siendo un campo obligatorio de construir (sin default), solo que su
valor puede ser `None`.

### Parseo (`src/faro/parseo.py`)

`extraer_deprecacion` ya maneja el caso (`if not doc: return None`). Solo cambia su
anotación de tipo a `doc: str | None`. Sin cambio de comportamiento.

### Adaptador (`src/faro/fuentes/local.py`)

Sin cambios de lógica: `s["doc"]` ahora puede ser `None` y se propaga tal cual a
`EntradaSimbolo.doc`, y `extraer_deprecacion(s["doc"])` lo tolera.

### Presentación (`src/faro/presentacion.py`)

`formatear()`, rama `Fragmento`: cuando `texto is None`, el cuerpo se reemplaza por un
aviso en vez de intentar limpiar/recortar `None`:

```
faro 0.1.0 :: faro.resolver.ResolverDeDocs.buscar_doc
buscar_doc(libreria: str, version: str, consulta: str) -> Fragmento | Ambiguo | NoEncontrado

[este símbolo no declara documentación]
```

Con texto presente, la salida no cambia en nada.

`formatear_verificaciones()`: sin cambios (decisión 2).

### Fixture (`src/faro/fuentes/fake.py`)

Se agrega una entrada sin doc a `simbolos_de_prueba()` para que el núcleo pueda
probar el camino sin depender de red, con un símbolo real de SQLAlchemy que
efectivamente no tiene docstring: `sqlalchemy.engine.Connection.commit_prepared`.

## Testing

**Extractor (`tests/test_extractor.py`), sin red:**
- Un símbolo sin docstring aparece en la salida con `doc=None` y su firma presente.
  Fixture: se agrega a `paquete_prueba` una función/método público sin docstring.
- Un símbolo con docstring sigue igual (protege contra regresión).

**Presentación (`tests/test_presentacion.py`):**
- `Fragmento` con `texto=None` muestra el aviso y conserva cita y firma.
- `Fragmento` con texto produce exactamente la misma salida que hoy.

**Resolver (`tests/test_resolver_buscar.py`):**
- `buscar_doc` sobre la entrada sin doc del fixture devuelve `Fragmento`, no
  `NoEncontrado`, y su `texto` es `None`.

**Contrato, SQLAlchemy real (`tests/test_contrato.py`):**
- `Connection.commit_prepared` existe en 2.0.36 y no tiene docstring: debe resolver
  como `Fragmento` (hoy da `NoEncontrado`).

**Contrato, Faro sobre Faro (`tests/test_contrato.py`) — el caso que lo encontró:**
- `buscar_doc("faro", <su versión>, "ResolverDeDocs.buscar_doc")` devuelve `Fragmento`.
  Convierte la sesión de dogfooding en una regresión permanente: si Faro vuelve a
  declararse inexistente a sí mismo, el test se cae.

## Fuera de alcance (explícito)

- No se marca "sin documentación" en `verificar_simbolos` (decisión 2).
- No se intenta rellenar documentación faltante desde ninguna otra fuente (la web
  sigue siendo no-objetivo; un símbolo sin docstring simplemente no tiene doc).
- No se cambia la regla de resolución exacto/sufijo, aunque el catálogo crezca.
