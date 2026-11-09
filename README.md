# Faro

> Servidor MCP de **documentación viva**: le da al asistente de IA una ventana para
> leer la documentación real y vigente de una librería en el momento, en vez de citarla
> de memoria desde su fecha de corte.

*(Un faro no navega por ti: te deja ver dónde está la costa en la niebla. Este servidor
no reentrena al modelo: le da luz sobre la documentación real para que no navegue de
memoria.)*

---

## El problema que resuelve

Un modelo de lenguaje tiene una **fecha de corte**. Todo lo que "sabe" de SQLAlchemy o
FastAPI es una foto congelada, mezclada de miles de ejemplos de versiones distintas. El
peligro no es solo estar desactualizado: el modelo **no distingue con fiabilidad qué
recuerda bien y qué está rellenando**. Puede darte la API de una versión vieja con la
misma seguridad que la actual.

Faro no reentrena ni "actualiza" al modelo; eso es imposible desde fuera. Le da una
**herramienta** para consultar la documentación real cuando la respuesta lo necesita. La
diferencia es la que hay entre citar un libro de memoria y tenerlo abierto en la mano.

## Así responde

**Detecta API obsoleta** que el modelo daría por buena:

```text
sqlalchemy 2.0.36 :: sqlalchemy.orm.Query.get
definido en: sqlalchemy 2.0.36
⚠ DEPRECADO desde 2.0 — usar Session.get
get(ident: '_PKIdentityArgument') -> 'Optional[Any]'

Return an instance based on the given primary key identifier,
or ``None`` if not found.
...
```

**Se niega a servir la versión equivocada.** Si el asistente da por hecho que usas la 1.4
y tienes instalada la 2.0.36:

```text
NO ENCONTRADO. Pediste 'sqlalchemy' 1.4, pero el entorno tiene 2.0.36. No sirvo doc de una versión que no es la tuya.
```

**Verifica afirmaciones** sobre la API, vengan de donde vengan:

```text
Query.get: existe (sqlalchemy.orm.Query.get) — ⚠ DEPRECADO desde 2.0, usar Session.get — get(ident: '_PKIdentityArgument') -> 'Optional[Any]'
URL.create: existe (sqlalchemy.engine.URL.create) — create(drivername: 'str', username: 'Optional[str]' = None, ...) -> 'URL'
Session.query_magic: NO EXISTE en esta versión.
```

## Principio rector: verificabilidad, no confianza ciega

> Un MCP de documentación no vuelve infalible al asistente. Le da algo a lo que agarrarse.

Un buen servidor cita la versión y el origen, para que el humano pueda verificar. Uno malo
—o uno que trae la documentación de otra versión— hace que el asistente **se equivoque con
más confianza todavía**. Por eso Faro:

1. **Exige la versión siempre.** Nunca devuelve "la última" de forma implícita. La versión
   que pides se trata como una *afirmación* y se contrasta con la que hay instalada.
2. **Cita la fuente en cada respuesta**: la versión exacta del paquete que se leyó.
3. **Falla con honestidad.** Si no tiene la versión pedida, dice "no la tengo"; nunca la
   sustituye en silencio por otra. Un "no encontrado" honesto vale más que un fragmento
   plausible de otra versión.

## Cómo funciona

Faro lee los docstrings del **paquete realmente instalado en el entorno de tu proyecto**.
No busca en la web y no tiene caché: el paquete instalado es la fuente de verdad. Eso da
la versión exacta (`2.0.36`, no "2.0"), los avisos de obsolescencia que la propia librería
declara con `.. deprecated::` y la firma real de cada función.

Funciona con **cualquier librería de Python instalada**. SQLAlchemy tiene una lista curada
de módulos (para no traer ruido de dialectos internos o utilidades de testing); cualquier
otra librería descubre sus submódulos automáticamente.

### Arquitectura

```
Claude Code ──MCP (stdio)──► servidor.py ──► núcleo: resolver · dominio · parseo · catalogo
                                                  │
                                                  ▼  puerto FuenteDeDocs
                                             FuenteLocal ──subproceso──► extractor.py
                                                                        (en el venv de tu proyecto)
```

- **El núcleo no importa `subprocess`, `httpx` ni `mcp`** (*Dependency Rule*). Habla con un
  puerto, `FuenteDeDocs`, y por eso se testea entero sin red ni subprocesos.
- **El extractor corre en un subproceso** con el intérprete de tu proyecto y solo usa la
  librería estándar. Importar un paquete ejecuta su código, y eso no debe pasar dentro
  del proceso de Faro.

## Instalación y uso

Requisitos: Python 3.12+ y [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/MC-Sinclair/faro.git
cd faro
uv sync
```

El repo incluye un `.mcp.json`, así que Claude Code detecta el servidor al abrir esta
carpeta. Para usarlo desde otro proyecto, añade una entrada equivalente en el `.mcp.json`
de ese proyecto, con `--directory` apuntando a donde clonaste Faro.

Indica a Faro qué entorno debe leer con `FARO_PYTHON`:

```bash
# Windows
set FARO_PYTHON=C:\ruta\a\tu-proyecto\.venv\Scripts\python.exe

# macOS / Linux
export FARO_PYTHON=/ruta/a/tu-proyecto/.venv/bin/python
```

Si no la configuras, Faro lee su propio entorno y **te avisa en cada respuesta**.

### Herramientas

- `listar_versiones(libreria)`: qué versión hay instalada de verdad.
- `buscar_doc(libreria, version, consulta)`: documentación y firma de un símbolo.
  `version` es obligatoria y **se verifica**: si indicas una versión que no es la
  instalada, Faro te lo dice y no devuelve nada.
- `verificar_simbolos(libreria, version, simbolos)`: contrasta afirmaciones sobre la API
  (incluidas las de la memoria del modelo) con el paquete instalado.

## Tests

```bash
uv run pytest -m "not contrato"   # 99 tests: núcleo, sin red ni SQLAlchemy
uv run pytest -m contrato         # 13 tests contra SQLAlchemy 2.0.36 real
```

Los tests del núcleo usan `FuenteFake`, con datos reales de SQLAlchemy 2.0.36 congelados
como fixtures. Los de contrato lanzan el extractor de verdad, e incluyen pasar Faro por
encima de su propio código.

## Cómo se construyó

Faro nació de un error real. Durante el diseño se afirmó **de memoria y con total
seguridad** que `Query.get` no existía en SQLAlchemy 2.0. Al comprobarlo contra el paquete
instalado, sí existe: está marcado como obsoleto. Es justo el fallo que Faro quiere
evitar, cometido mientras se diseñaba. Ese caso es hoy el test de contrato central del
proyecto.

El proceso:

- **Diseño antes que código.** Una fase de *brainstorming* cerró las decisiones clave:
  construir en vez de usar un MCP de terceros, Python en lugar de TypeScript, y el paquete
  instalado en lugar de la web como fuente. Cada decisión está razonada y documentada.
- **Spec y plan escritos** para la v1 y para cada mejora posterior, en
  [`docs/superpowers/`](docs/superpowers/).
- **TDD tarea a tarea**: la v1 se construyó en 11 tareas, cada una con sus tests primero y
  su commit.
- **Dogfooding.** Usar Faro contra sí mismo y contra casos reales destapó varios defectos
  que los tests no veían, casi todos de la misma familia: Faro afirmaba algo falso con
  seguridad en lugar de mostrar el dato real que tenía. Por ejemplo, métodos heredados o
  `classmethod` que daban "no existe", o una obsolescencia que se perdía en las respuestas
  ambiguas. Cada uno se corrigió con su spec y sus tests.
- **Desarrollo asistido por IA** con [Claude Code](https://claude.com/claude-code) como
  pareja de programación. Yo dirijo el problema, las decisiones de diseño y la revisión;
  el asistente ejecuta sobre un plan aprobado, y cada cambio pasa por tests y revisión
  antes de entrar. El `CLAUDE.md` del repo es el contexto que le doy: arquitectura,
  reglas y el porqué de cada decisión.
- **Commits pequeños** con formato *Conventional Commits* (`feat:`, `fix:`, `docs:`...).

## Límites conocidos

- Solo referencia de API. **No busca en tutoriales ni guías de migración.**
- Solo conoce versiones **instaladas**. No se inventa las que no están.
- Solo paquetes de Python.
- Solo avisa de obsolescencia si la librería la **declara** con `.. deprecated::`.
- No infiere tipos. Es una decisión consciente: sería otro sitio donde Faro podría
  deducir mal y afirmar algo falso con seguridad.

## Licencia

[MIT](LICENSE)
