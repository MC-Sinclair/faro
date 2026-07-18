# Faro

> Servidor MCP de **documentación viva**: le da al asistente de IA una ventana para
> leer la doc real y vigente de una librería en el momento, en vez de citarla de
> memoria desde su fecha de corte.

*(Un faro no navega por vos: te deja ver dónde está la costa en la niebla. Este
servidor no reentrena al modelo — le da luz sobre la documentación real para que no
navegue de memoria.)*

---

## El problema que resuelve

Un modelo de lenguaje tiene una **fecha de corte**. Todo lo que "sabe" de SQLAlchemy,
FastAPI o `node:sqlite` es una foto congelada, mezclada de miles de ejemplos de
versiones distintas. El peligro no es solo estar desactualizado: es que el modelo
**no distingue con fiabilidad qué recuerda bien y qué está rellenando**. Puede darte
una API de una versión vieja con la misma seguridad que la actual.

Vademécum no reentrena ni "actualiza" al modelo — eso es imposible desde fuera. Le da
una **herramienta** para ir a buscar el texto real de la documentación cuando la
respuesta lo necesita. La diferencia con su memoria es la que hay entre citar un libro
de memoria y tenerlo abierto en la mano.

## Por qué construirlo (y cuándo NO)

Sé honesto contigo mismo antes de empezar:

- **Ya existen** servidores MCP de documentación de terceros. Si lo único que querés
  es la capacidad, instalá uno con `/plugin` y listo — no construyas.
- **Construí Vademécum si** querés: (a) control total sobre *qué fuentes* se consultan
  y con qué versión (evitar que te sirvan la doc de una versión que no es la tuya),
  (b) un proyecto de aprendizaje real sobre el protocolo MCP, o (c) una herramienta a
  medida de tu stack, sin depender de un tercero cuya calidad de fuentes no controlás.

Esta decisión es la primera de la mesa de apuestas. No la saltes.

## Qué hace exactamente (v1 tentativa)

Expone, vía MCP, un puñado de herramientas al asistente. La forma mínima:

- `buscar_doc(libreria, version, consulta)` → devuelve el fragmento relevante de la
  documentación oficial, **anclado a esa versión**.
- `listar_versiones(libreria)` → qué versiones conoce, para que el asistente pida la
  que de verdad usás.

La salida **siempre cita fuente y versión**. Ese es el punto entero.

## Principio rector: verificabilidad, no confianza ciega

Este es el hilo que debe atravesar todo el diseño:

> Un MCP de docs no vuelve al asistente infalible. Le da de dónde agarrarse.

Un buen servidor cita la versión y la URL de origen, así el humano puede verificar.
Un mal servidor —o uno que trae la doc de la versión equivocada— hace que el asistente
**yerre con más confianza todavía**. Por eso Vademécum debe:

1. **Fijar versión siempre.** Nunca devolver "la última" implícita; que el consumidor
   la pida explícita.
2. **Citar la fuente en cada respuesta** (URL + versión + fecha de la doc).
3. **Fallar honestamente.** Si no tiene la versión pedida, decir "no la tengo",
   nunca aproximar en silencio con otra. Un `null` honesto vale más que un fragmento
   plausible pero de otra versión.

## Alcance v1 — empezá por tu propia necesidad

No intentes cubrir "todas las librerías". Apuntá al *público hambriento*: las
librerías donde tu memoria (y la mía) es más floja y el coste de un error es alto.
Candidatas evidentes, sacadas de tus proyectos actuales:

| Librería | Proyecto | Por qué duele el desfase |
|---|---|---|
| SQLAlchemy 2.x | InvestSim | La 2.x cambió la API respecto a 1.4; hay muchísimo ejemplo viejo |
| FastAPI | InvestSim (F4) | Evoluciona rápido |
| API de Claude / Anthropic | InvestSim (F3) | Modelos y params cambian seguido |
| `node:sqlite` | taskDir | Módulo nuevo, poco documentado en el entrenamiento |

Una sola de estas, bien resuelta de punta a punta, es una v1 legítima.

## Arquitectura (tentativa — a decidir en el brainstorming)

Leaning inicial, siguiendo la misma Dependency Rule que InvestSim: el núcleo (la
lógica de "resolver una consulta de doc a un fragmento con fuente") **no depende** de
cómo se obtiene la doc ni de cómo se transporta al asistente. Ambos son detalles
enchufables tras interfaces:

```
Cliente MCP (Claude Code, …)
        │  protocolo MCP
        ▼
   Capa MCP (transporte)  ──►  Núcleo: ResolverDeDocs
                                     │
                            ┌────────┴─────────┐
                            ▼                  ▼
                     FuenteDeDocs         Caché/Índice
                  (fetch web, repo         (local, para
                   local, paquete)          no re-fetchear)
```

Esto permite testear el núcleo sin red y sin un cliente MCP real — igual que InvestSim
testea su bucle con `FakeMarketDataProvider`. La `FuenteDeDocs` tendrá su propio
`FakeFuente` para los tests.

## Decisiones abiertas (para la mesa de apuestas)

- **¿Construir o instalar uno existente?** (ver arriba — decisión #1).
- **Lenguaje/runtime del servidor:** ¿Python (coherente con InvestSim) o Node
  (coherente con taskDir y con el ecosistema MCP)? Impacta todo lo demás.
- **Fuente de la doc:** ¿fetch de la web oficial en vivo, indexar un repo/paquete
  local, o snapshots versionados? Trade-off frescura vs. reproducibilidad.
- **Estrategia de caché:** ¿cuánto tiempo vive un fragmento antes de re-verificar?
- **Alcance de una v1:** ¿una sola librería de la tabla, o el mecanismo genérico?

## Primer paso real (con una ironía de fondo)

El primer paso técnico es **leer la especificación actual del protocolo MCP y del SDK
que uses** — porque mi conocimiento de esos detalles también está en la cápsula del
tiempo y no es fiable. Es decir: el primer acto de construir Vademécum es hacer a mano,
una vez, exactamente lo que Vademécum automatizará. Bien podés usar `WebFetch` o la
skill `claude-api` para traer la doc vigente de MCP antes de escribir una línea.

No aceptes de mí (ni de ningún modelo) la API del SDK de MCP de memoria. Verificala.

## Flujo de trabajo

Este README es solo la **semilla**, no la spec. Seguí tu proceso de siempre:

1. `brainstorming` → cerrar las decisiones abiertas de arriba, sobre todo la #1.
2. `writing-plans` → convertir la spec en un plan por tareas.
3. Ejecución **TDD** → como en InvestSim, con el núcleo testeado sin red.

Cuando exista código, copiá el patrón de `.graphifyignore` de los otros proyectos para
mantener limpio el grafo, y `graphify extract . --code-only` para arrancarlo.

---

## Uso (v1)

Faro lee los docstrings del paquete **instalado en el entorno de tu proyecto**.
Apuntalo con `FARO_PYTHON`:

```bash
# Windows
set FARO_PYTHON=C:\ruta\a\investsim\.venv\Scripts\python.exe

# macOS / Linux
export FARO_PYTHON=/ruta/a/investsim/.venv/bin/python
```

Si no lo configurás, Faro lee su propio entorno y **te avisa en cada respuesta**.

### Herramientas

- `listar_versiones(libreria)` — qué versión está instalada de verdad.
- `buscar_doc(libreria, version, consulta)` — doc de un símbolo. `version` es
  obligatorio y **se verifica**: si declarás una versión que no es la instalada,
  Faro te lo dice y no devuelve nada.
- `verificar_simbolos(libreria, version, simbolos)` — contrasta afirmaciones sobre
  la API (vengan de donde vengan, incluida la memoria del modelo) contra el paquete
  instalado.

### Tests

```bash
uv run pytest -m "not contrato"   # ciclo rápido: núcleo, sin red ni SQLAlchemy
uv run pytest -m contrato         # contra SQLAlchemy 2.0.36 real
```

### Límites conocidos de la v1

- Solo referencia de API. **No busca en tutoriales ni guías de migración.**
- Solo sabe de versiones **instaladas**. No inventa las que no están.
- Solo paquetes Python. `node:sqlite` queda fuera por construcción.
- Solo avisa de obsolescencia si la librería la **declara** con `.. deprecated::`.
