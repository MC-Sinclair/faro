# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado actual

v1 implementada. Servidor MCP funcionando sobre stdio con tres herramientas.

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

**La regla de oro al tocar este código:** el núcleo (`resolver.py`, `dominio.py`,
`parseo.py`, `catalogo.py`) **no importa `subprocess`, ni `httpx`, ni `mcp`**. Si un
test del núcleo necesita red o subprocesos, el diseño se rompió.

## Qué es Faro (definición final, no la del README)

Un servidor MCP que **lee los docstrings del paquete de Python realmente instalado en el venv del
proyecto del usuario** y responde con la versión exacta, el símbolo cualificado, y cualquier aviso
de deprecación que la propia librería declare. No busca en la web. No tiene caché. El artefacto
instalado es la fuente de verdad.

Librería objetivo de la v1: **SQLAlchemy 2.x**, ya con el paquete verificado localmente (`2.0.36`).

## Las cinco decisiones cerradas, y por qué (esto YA NO es material de brainstorming)

1. **Construir, no instalar un MCP de terceros.** Motivo del usuario: aprender el protocolo MCP +
   tener control real de fuentes/versiones. Ver sección "Cómo se complementa con Context7" abajo.
2. **Python + `uv`**, no TypeScript. Verificado con la doc oficial de MCP: ambos SDK son **Tier 1**,
   así que "Node va primero en el ecosistema MCP" no es un desempate real. Ganó Python porque (a)
   menos ceremonia de tooling que TypeScript+Zod+tsconfig, y sobre todo (b) **es el único que permite
   introspeccionar un paquete Python en proceso** — esto resultó ser la razón decisiva, ver punto 4.
3. **SQLAlchemy 2.x** como librería objetivo, no FastAPI ni `node:sqlite` ni la API de Claude. Motivo:
   es la única candidata donde el anclaje de versión es *comprobable* — 1.4/2.0/2.1 tienen APIs
   distintas y hay dolor real de InvestSim.
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

## Arquitectura (ya no tentativa — ver la spec para el diagrama completo)

Dependency Rule. El núcleo (`resolver.py`, `dominio.py`, `parseo.py`, `catalogo.py`) **no importa
`subprocess`, `httpx` ni `mcp`**. Habla con el puerto `FuenteDeDocs` (`Protocol`). Producción usa
`FuenteLocal`, que lanza un **subproceso** con el intérprete del proyecto objetivo (`FARO_PYTHON`)
ejecutando `extractor.py` — un script aparte que solo usa stdlib, porque corre dentro de un venv
ajeno y porque importar un paquete ejecuta su código de módulo (no debe pasar dentro del proceso de
Faro). Tests usan `FuenteFake` con datos reales de SQLAlchemy 2.0.36 congelados como fixtures.

Regla dura para cualquier cambio futuro: **si un test del núcleo necesita red o subprocesos, el
diseño se rompió.**

## Comandos (una vez implementado — ver Task 11 del plan)

```bash
uv sync                          # instalar
uv run pytest -m "not contrato"  # ciclo rápido de TDD (núcleo, sin red)
uv run pytest -m contrato        # tests contra SQLAlchemy 2.0.36 real
uv run python -m faro.servidor   # arrancar el servidor
```

`FARO_PYTHON` = ruta al intérprete del proyecto que se quiere consultar (p. ej. el venv de InvestSim).
Sin esa variable, Faro lee su propio entorno y lo advierte en cada respuesta — nunca lo hace en
silencio.

## graphify

`graphify-out/` existe pero está **vacío** (solo `cache/`, sin `graph.json`): se corrió
`graphify extract . --code-only` antes de escribir código, y con 0 archivos de código dio
"graph is empty" (exit 1). Es esperado — no es un fallo a investigar.

**Si después de generar o modificar código (Task 1 en adelante) `graphify-out/` sigue sin
`graph.json` / los demás `.json`** (ya sea porque el hook de `update` no corrió, o corrió antes
de que el código existiera, o falló en silencio), **relanzar a mano**:

```bash
graphify extract . --code-only
```

`graphify-out/` está en `.gitignore`: no se comitea, así que su ausencia tras un `git pull` /
`checkout` también es normal — hay que regenerarlo con el comando de arriba.

## No-objetivos explícitos de la v1 (no proponer estas features sin pasar por brainstorming)

- Nada de búsqueda en prosa/tutoriales/guías de migración — solo referencia de API.
- Nada de versiones no instaladas — Faro puede sugerir instalarlas, nunca inventa su contenido.
- Nada de librerías no-Python (`node:sqlite` queda fuera por construcción de esta v1).
- No juzga idiomaticidad más allá de lo que la librería declara con `.. deprecated::`.

## Convenciones

- **Todo en español**: código, nombres de herramientas MCP (`buscar_doc`, `listar_versiones`,
  `verificar_simbolos`), mensajes al usuario, commits.
- Python `>=3.12`, gestionado con `uv` (no `pip`/`venv` a mano).
- Commits en español, formato imperativo, con `Co-Authored-By` cuando los genera Claude.
