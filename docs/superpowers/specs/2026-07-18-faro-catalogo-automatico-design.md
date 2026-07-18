# Faro — catálogo automático (design)

## Contexto y motivación

Hoy Faro solo funciona bien con SQLAlchemy: `catalogo.py` tiene una única entrada
curada a mano, y cualquier otra librería cae en un fallback pobre
(`local.py` manda `modulos=[libreria]`, escaneando solo el módulo top-level, sin
sus submódulos reales). El propio `catalogo.py` lo dice en su docstring: "Agregar
FastAPI mañana es agregar una entrada acá" — pero eso significa mantener a mano
una lista de módulos por cada librería que alguien quiera usar con Faro.

Este diseño hace que **cualquier librería instalada** funcione razonablemente bien
sin necesidad de una entrada manual, descubriendo sus submódulos automáticamente.

## Decisiones (ya cerradas con el usuario)

1. **Híbrido.** SQLAlchemy conserva su entrada curada en `CATALOGO` (gana siempre
   que exista — cero riesgo de regresión en el caso ya afinado). El descubrimiento
   automático es el *fallback* para cualquier librería sin entrada manual.
2. **Un solo mensaje de fallo: "no está instalada".** Se elimina el gate previo
   contra el catálogo estático (`_verificar_catalogo`) — ya no tiene sentido
   cuando "conocer" una librería no depende de una lista cerrada. El único
   chequeo real es si está instalada de verdad en el entorno objetivo.
3. **Sin tope artificial de profundidad/cantidad** al caminar submódulos. El
   timeout del subproceso (`_TIMEOUT_SEG = 120` en `local.py`) y el try/except
   por módulo roto (ya existentes) son la protección.

## Diseño

### Por qué el descubrimiento vive en `extractor.py`, no en `local.py`

`local.py` corre en el proceso de Faro, que no tiene instalada la librería del
proyecto objetivo — no puede importarla para inspeccionar su `__path__`. Solo el
subproceso (que corre con el intérprete del proyecto objetivo) puede hacerlo. Por
eso el descubrimiento tiene que pasar dentro de `extractor.py`.

### Contrato del extractor: `modulos: null` como señal

`local.py._extraer()` cambia su fallback: en vez de mandar `modulos=[libreria]`
para librerías sin entrada en `CATALOGO`, manda `modulos=None` (JSON `null`) —
una señal de "no tengo una lista fija para esto, descubrila vos".

```python
entrada = CATALOGO.get(libreria)
modulos = list(entrada.modulos) if entrada else None
peticion = json.dumps({"libreria": libreria, "modulos": modulos})
```

`extractor.py.main()`:

```python
libreria = peticion["libreria"]
version = version_de(libreria)
modulos = peticion.get("modulos")
if modulos is None:
    modulos = _descubrir_modulos(libreria) if version is not None else []
simbolos = extraer(modulos) if version is not None else []
```

Nueva función:

```python
def _descubrir_modulos(libreria: str) -> list[str]:
    """Para librerías sin entrada curada en catalogo.py: camina sus submódulos
    públicos automáticamente. La curación manual (SQLAlchemy) sigue ganando
    cuando existe — esto solo corre cuando el caller no mandó una lista fija.
    """
    modulos = [libreria]
    try:
        paquete = importlib.import_module(libreria)
    except Exception:
        return modulos

    ruta = getattr(paquete, "__path__", None)
    if ruta is None:
        return modulos  # módulo simple (p. ej. textwrap): no hay submódulos

    for info in pkgutil.walk_packages(ruta, prefix=f"{libreria}.", onerror=lambda _: None):
        if any(parte.startswith("_") for parte in info.name.split(".")):
            continue
        modulos.append(info.name)
    return modulos
```

Requiere `import pkgutil` (stdlib) en `extractor.py`.

### `catalogo.py`: sin cambios

Sigue exactamente como está — la entrada de SQLAlchemy no se toca.

### `resolver.py`: se elimina el gate de catálogo

Se elimina `_verificar_catalogo()` y sus tres llamadas (en `listar_versiones`,
`buscar_doc`, `verificar_simbolos`), y el parámetro `catalogo` del constructor de
`ResolverDeDocs` (junto con el import de `CATALOGO`/`EntradaCatalogo`, que deja de
usarse en este archivo — pasa a ser un dato consumido únicamente por `local.py`).

`listar_versiones` queda:

```python
def listar_versiones(self, libreria: str) -> list[str] | NoEncontrado:
    instalada = self._fuente.version_instalada(libreria)
    if instalada is None:
        return NoEncontrado(motivo=f"'{libreria}' no está instalada en el entorno objetivo.")
    return [instalada]
```

`buscar_doc` y `verificar_simbolos` pierden su llamada a `_verificar_catalogo`
(que se disparaba antes del `_guarda_de_version`) — el chequeo de "instalada"
que ya hace `_guarda_de_version` cubre lo mismo, con el mismo mensaje.

### Efecto en cadena sobre `FuenteFake`

`FuenteFake.version_instalada(libreria)` hoy devuelve `self._version` sin mirar
`libreria` — funcionaba porque el gate de catálogo interceptaba cualquier
libreria distinta de "sqlalchemy" antes de llegar a la fake. Sin el gate, la fake
necesita discriminar:

```python
class FuenteFake:
    def __init__(self, version, entradas, libreria: str = "sqlalchemy") -> None:
        self._version = version
        self._entradas = entradas
        self._libreria = libreria

    def version_instalada(self, libreria: str) -> str | None:
        return self._version if libreria == self._libreria else None

    def simbolos(self, libreria: str) -> list[EntradaSimbolo]:
        return list(self._entradas) if libreria == self._libreria else []
```

El default `libreria="sqlalchemy"` mantiene compatibles todos los usos actuales
de `FuenteFake(version=..., entradas=...)` sin tocarlos.

### Tests existentes que cambian de aserción

- `tests/test_resolver_buscar.py::test_libreria_desconocida_falla_honestamente`
- `tests/test_resolver_version.py::test_listar_versiones_de_libreria_desconocida_falla_honestamente`

Ambos consultan `"django"` (no instalada) y hoy afirman que el mensaje menciona
"sqlalchemy" (el catálogo de librerías conocidas). Pasan a afirmar que el mensaje
dice "no está instalada" — sin submención de "sqlalchemy", que ya no tiene
sentido en el mensaje.

## Testing (nuevo)

**Extractor, sin red:**
- Descubrimiento automático sobre el paquete stdlib `json` (submódulos reales:
  `json.decoder`, `json.encoder`, `json.scanner`) encuentra símbolos de esos
  submódulos.
- La fixture local `paquete_prueba` gana un submódulo privado (`_interno.py`);
  el descubrimiento automático debe excluirlo.
- Una librería sin `__path__` (módulo simple, p. ej. `textwrap`) no rompe:
  cae de vuelta a `[libreria]`.

**`FuenteLocal`, contra un venv real (`tests/test_fuente_local.py`):**
- `email.mime.text.MIMEText` se encuentra vía `fuente.simbolos("email")`, sin
  estar en ningún catálogo — y sin estar re-exportada en el `email` top-level
  (verificado: `"MIMEText" not in dir(email)`), así que esto prueba de verdad
  que caminó el submódulo, no que escaneó solo el paquete raíz.

**`FuenteFake` (`tests/test_fuente_fake.py`):**
- Nuevo test: preguntar por una librería distinta a la configurada devuelve
  `None`/`[]`.

**Resolver:** actualizar las dos aserciones de mensaje mencionadas arriba.

## Fuera de alcance (explícito)

- No se agrega ningún tope de profundidad/cantidad de submódulos (decisión ya
  cerrada arriba).
- No se cambia nada de la entrada curada de SQLAlchemy.
- No se resuelve acá la idea de auditar bloques de código completos — es una
  mejora futura, no parte de esta lista de tres.
