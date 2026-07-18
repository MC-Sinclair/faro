# Faro — herencia en el extractor (design)

## Contexto y motivación

Usando Faro contra sí mismo (dogfooding) se detectó que consultas legítimas sobre
métodos heredados devuelven `NoEncontrado` aunque el método existe de verdad. Caso
verificado contra SQLAlchemy 2.0.36 real:

```
CursorResult.fetchall  -> NoEncontrado   (existe: heredado de Result)
CursorResult.scalar    -> NoEncontrado   (existe: heredado de Result)
```

La causa: `src/faro/fuentes/extractor.py` recorre, por cada clase encontrada en un
módulo, solo `vars(clase)` — el diccionario **propio** de la clase. Los métodos
heredados y no sobreescritos no viven ahí; viven en el `__dict__` de la clase base.

Este es el mismo tipo de falso negativo que fundó el proyecto (`Query.get`) y que ya
se corrigió una vez para re-exports (Connection.execute, URL.create). Es, en la
práctica, la misma enfermedad en un tercer lugar del código: el extractor no ve todo
lo que la clase realmente expone.

## Decisiones (ya cerradas con el usuario)

1. **Transparencia: simple, sin marcar procedencia.** Un método heredado se muestra
   igual que uno propio — sin un aviso tipo "heredado de Result". Esto evita tocar
   el modelo de dominio (`EntradaSimbolo`, `Fragmento`) y la capa de presentación.
2. **Profundidad: toda la cadena de herencia (`__mro__`), no solo el padre directo.**
   Cubre el caso real (`ChunkedIteratorResult` → `IteratorResult` → `Result` → ...)
   sin depender de cuántos niveles tenga la jerarquía real de la librería.

## Diseño

**Archivo afectado:** `src/faro/fuentes/extractor.py` únicamente. No toca
`dominio.py`, `resolver.py`, `presentacion.py`, ni el mecanismo de deduplicación por
identidad de re-exports (Task de la revisión final, ya en `master`) — son
ortogonales: ese fix dedupe **clases** re-exportadas en dos módulos; este fix hace
que cada clase, una vez elegida como canónica, exponga también los métodos que
hereda.

**Algoritmo:** la función que hoy anota los miembros de una clase (dentro de
`extraer()`) deja de iterar únicamente `vars(objeto).items()` y pasa a iterar
`objeto.__mro__` completo, de la clase más específica a `object`, registrando cada
nombre de miembro **la primera vez que aparece**. Como Python coloca la propia
clase primero en su `__mro__`, esto reproduce exactamente la regla de resolución de
atributos de Python: si una subclase sobreescribe un método, gana su versión (su
propio docstring); si no lo sobreescribe, gana la versión heredada de la clase base
donde efectivamente vive.

Pseudocódigo del cambio (reemplaza el bucle interno de miembros de clase):

```python
def _anotar_miembros(vistos: dict[str, str], nombre_clase: str, clase: type) -> None:
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
                _anotar(vistos, f"{nombre_clase}.{nombre_attr}", attr)
```

La detección de `classmethod`/`staticmethod`/`property` se mantiene igual que hoy
(sobre el descriptor crudo de `vars(base)`, no sobre un `getattr` resuelto) —
por eso se itera manualmente el MRO en vez de usar `inspect.getmembers`, que
devolvería los descriptores ya resueltos (perdiendo la distinción classmethod vs.
función plana que el fix anterior ya depende).

**Efecto secundario aceptado — tamaño del catálogo:** cada subclase concreta ahora
lista también los métodos que hereda sin sobreescribir. El catálogo de símbolos va
a crecer (se estima manualmente que podría duplicarse o triplicarse frente a los
~2593 símbolos actuales de SQLAlchemy). La extracción actual tarda ~1 segundo; un
crecimiento de ese orden no cambia la magnitud del tiempo de respuesta y no
requiere ningún cambio de diseño (sigue siendo un subproceso con un límite de
timeout ya generoso, `_TIMEOUT_SEG = 120` en `local.py`).

**Interacción con la ambigüedad (Regla 3):** un método heredado por múltiples
clases hermanas (p. ej. `dispose` en varias subclases de `Pool`) seguirá generando
`Ambiguo` si se consulta sin calificar el nombre de la clase — igual que hoy pasa
con `select`. Eso es correcto: son símbolos distintos (cada clase tiene su propia
identidad), simplemente ahora *cada uno* de ellos resuelve bien cuando se lo
consulta calificado (`CursorResult.fetchall`), que es el caso que este fix corrige.

## Testing

**Unitario, sin red (`tests/test_extractor.py`):** se extiende la fixture local
`tests/fixtures_extractor_dedupe/paquete_prueba/` (ya existe, usada por el fix de
re-exports) con una jerarquía de clases:

- `Base` con un método `metodo_base()`.
- `Hija` que hereda de `Base` sin sobreescribir `metodo_base` — debe resolver bajo
  `paquete_prueba.base.Hija.metodo_base` con el docstring de `Base`.
- `HijaConOverride` que hereda de `Base` y sí sobreescribe `metodo_base` con su
  propio docstring — debe resolver con **su propio** texto, no el de `Base`.

**De contrato, contra SQLAlchemy 2.0.36 real (`tests/test_contrato.py`):** el caso
que motivó este diseño —

```python
def test_metodos_heredados_resuelven_p_ej_cursorresult_fetchall(resolver):
    r = resolver.buscar_doc("sqlalchemy", "2.0.36", "CursorResult.fetchall")
    assert isinstance(r, Fragmento)
```

## Fuera de alcance (explícito)

- No se agrega ningún indicador de "heredado de X" en la salida (decisión ya
  cerrada arriba).
- No se toca el modelo de dominio ni la presentación.
- No se resuelve en este diseño el catálogo automático de librerías ni las firmas
  de función — son las siguientes dos mejoras de la lista, cada una con su propio
  diseño y plan.
