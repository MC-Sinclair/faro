# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado actual

**El repo está vacío salvo `README.md`.** No hay código, ni manifiesto de paquete, ni tests, ni
repositorio git inicializado. No hay comandos de build/lint/test que documentar todavía — cuando
existan, agregalos acá.

El `README.md` es la **semilla**, no la spec: fija el problema, el principio rector y las decisiones
que siguen abiertas. Leelo antes de proponer nada.

## Qué es Faro

Un servidor MCP de documentación viva: expone herramientas para que un asistente lea la doc real y
vigente de una librería (anclada a una versión concreta) en vez de citarla de memoria desde su fecha
de corte.

Forma mínima tentativa de la API: `buscar_doc(libreria, version, consulta)` y
`listar_versiones(libreria)`.

## Principio rector: verificabilidad, no confianza ciega

Este es el hilo que atraviesa todo el diseño. Un MCP de docs que trae la versión equivocada hace que
el asistente **yerre con más confianza todavía**. Por eso, cualquier código que escribas debe:

1. **Fijar versión siempre.** Nunca devolver "la última" implícita — que el consumidor la pida
   explícita.
2. **Citar la fuente en cada respuesta** (URL + versión + fecha de la doc).
3. **Fallar honestamente.** Si no tiene la versión pedida, decir "no la tengo". Nunca aproximar en
   silencio con otra: un `null` honesto vale más que un fragmento plausible pero de otra versión.

Si una decisión de diseño choca con alguno de estos tres puntos, gana el principio.

## No confíes en tu memoria del SDK de MCP

El conocimiento del modelo sobre el protocolo MCP y su SDK está en la misma cápsula del tiempo que
todo lo demás, y no es fiable. Antes de escribir una línea contra el SDK, traé la spec vigente
(`WebFetch`, o la skill `claude-api` para lo de Anthropic). El primer acto de construir Faro es hacer
a mano, una vez, exactamente lo que Faro automatizará.

## Decisiones abiertas (no las cierres solo)

Ninguna de estas está resuelta; son material de brainstorming con el usuario, no defaults que puedas
elegir por tu cuenta:

- **Construir vs. instalar uno existente.** Es la decisión #1 y el README la plantea en serio: ya
  existen MCP de docs de terceros. Construir se justifica por control de fuentes/versiones,
  aprendizaje del protocolo, o encaje a medida del stack.
- **Lenguaje/runtime:** Python (coherente con InvestSim) o Node (coherente con taskDir y el
  ecosistema MCP). Condiciona todo lo demás.
- **Fuente de la doc:** fetch web en vivo, indexar repo/paquete local, o snapshots versionados —
  frescura vs. reproducibilidad.
- **Estrategia de caché** y **alcance de la v1** (una sola librería de punta a punta es una v1
  legítima).

## Arquitectura tentativa

Dependency Rule, igual que InvestSim: el núcleo (resolver una consulta de doc a un fragmento con
fuente) **no depende** de cómo se obtiene la doc ni de cómo se transporta al asistente. Ambos son
detalles enchufables tras interfaces.

```
Cliente MCP  ──►  Capa MCP (transporte)  ──►  Núcleo: ResolverDeDocs
                                                   │
                                          ┌────────┴─────────┐
                                          ▼                  ▼
                                    FuenteDeDocs        Caché/Índice
```

La consecuencia práctica: el núcleo se testea **sin red y sin cliente MCP real**. `FuenteDeDocs`
tendrá un `FakeFuente` para tests, como InvestSim testea su bucle con `FakeMarketDataProvider`.

## Flujo de trabajo

El README lo fija explícitamente: `brainstorming` (cerrar las decisiones abiertas, sobre todo la #1)
→ `writing-plans` → ejecución **TDD** con el núcleo testeado sin red. No saltes al código.

Cuando exista código: copiar el patrón de `.graphifyignore` de los otros proyectos y arrancar con
`graphify extract . --code-only`.

## Convenciones

- **El proyecto se escribe en español** (README, y presumiblemente nombres de herramientas MCP como
  `buscar_doc` / `listar_versiones`). Mantené el idioma.
- El README todavía llama al proyecto **"Vademécum"** en varios párrafos del cuerpo — es el nombre
  viejo. El proyecto es **Faro**.
