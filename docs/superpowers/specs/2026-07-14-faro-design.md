# Faro — Diseño v1

**Fecha:** 2026-07-14
**Estado:** aprobado, listo para plan de implementación

---

## 1. Qué es

Un servidor MCP que responde preguntas sobre la API de una librería leyendo **los docstrings
del paquete realmente instalado en el entorno del proyecto del usuario**, y devuelve la
respuesta con su versión exacta y sus advertencias de obsolescencia.

No es un buscador de documentación. Es un **verificador de afirmaciones sobre la API** contra
el artefacto que el usuario tiene instalado.

## 2. El problema

Un modelo tiene fecha de corte, y lo que "sabe" de SQLAlchemy es una mezcla congelada de
ejemplos de versiones distintas. El peligro no es solo estar desactualizado: el modelo **no
distingue con fiabilidad qué recuerda bien y qué está rellenando**. Sirve la API de 1.4 con la
misma confianza que la de 2.0.

Este fallo ocurrió literalmente durante el diseño de este documento: al proponer un caso de
prueba, el asistente afirmó con total seguridad que `Query.get` no existía en SQLAlchemy 2.0.
Sí existe (documentado como legacy). El error se detectó solo porque se verificó contra la
fuente real. Ese incidente es el caso de aceptación nº1 de este proyecto.

## 3. Principio rector

> Un MCP de docs no vuelve infalible al asistente. Le da de dónde agarrarse. Uno que trae la
> versión equivocada lo hace errar **con más confianza todavía**.

Tres reglas, en orden de prioridad. Si una decisión de diseño choca con alguna, gana la regla:

1. **Fijar versión siempre.** Nunca "la última" implícita. El consumidor la declara explícita.
2. **Citar la fuente en cada respuesta** (paquete + versión exacta + símbolo cualificado).
3. **Fallar honestamente.** Si no se tiene lo pedido, decirlo. Nunca aproximar en silencio. Un
   `NoEncontrado` honesto vale más que un fragmento plausible de otra versión.

## 4. Decisiones tomadas

| Decisión | Elección | Motivo |
|---|---|---|
| ¿Construir o instalar uno existente? | **Construir** | Aprender el protocolo MCP + control real sobre qué doc/versión se consulta |
| Lenguaje/runtime | **Python + uv** | Ambos SDK son Tier 1 (verificado); Python tiene menos ceremonia de tooling, reusa el músculo de InvestSim (pytest, Dependency Rule), y **es el único que habilita la introspección de paquetes Python** |
| Librería objetivo v1 | **SQLAlchemy 2.x** | Es la que pone a prueba el anclaje de versión de verdad: la 2.x rompió API respecto a 1.4 y hay muchísimo ejemplo viejo circulando. Dolor real en InvestSim |
| Fuente de la doc | **Paquete instalado (introspección)** | Máxima fiabilidad y replicabilidad; versión exacta; trae metadatos de deprecación gratis |
| Caché | **Ninguna en v1** | El venv *es* la caché. El artefacto instalado es inmutable |

### 4.1 Por qué el paquete instalado y no la web

Se evaluaron tres fuentes web (fetch en vivo, snapshot completo, índice `objects.inv` + fetch
dirigido) y se diseñó la tercera antes de descubrir que existía una cuarta opción, mejor.

Comparación verificada con datos reales:

| | Paquete instalado | Índice web (`objects.inv`) |
|---|---|---|
| Símbolos de API | ~2.763 | 4.349 |
| Prosa / narrativa | ninguna | 1.116 secciones |
| Metadatos de deprecación | **sí** | no |
| Versión | **exacta (`2.0.36`)** | aproximada (`2.0`) |
| ¿Se puede romper? | no | sí (rediseño del sitio, cambio de markup) |
| ¿Necesita red? | no | sí |

De 1.500 símbolos del índice web muestreados, 1.192 (79%) tienen docstring accesible.

**El índice web cubre más superficie; el paquete instalado da más certeza.** Como Faro nace
precisamente porque *la certeza es el problema*, gana el paquete.

La fuente web queda **diseñada pero no construida**: entra como un segundo adaptador tras el
puerto `FuenteDeDocs` cuando se quiera prosa, versiones no instaladas, o librerías no-Python.

## 5. Arquitectura

Dependency Rule: el núcleo no sabe qué es MCP ni qué es un subproceso.

```
Cliente MCP (Claude Code)
      │  stdio
      ▼
 Capa MCP (FastMCP)  ──►  ResolverDeDocs   ← núcleo: sin red, sin subprocesos
                                │
                        ┌───────┴────────┐
                        ▼                ▼
                  FuenteDeDocs        Catálogo        ← puerto (Protocol) + data
                        │
              ┌─────────┴─────────┐
        FuenteLocal          FuenteFake
      (subproceso →           (tests)
       extractor.py)
```

**`FuenteLocal` corre un subproceso** con el intérprete del proyecto objetivo, que ejecuta
`extractor.py` y devuelve JSON. Dos razones, ambas necesarias:

1. Faro puede introspeccionar **cualquier venv** (el de InvestSim, por ejemplo), no solo el suyo.
2. **No se importa código de terceros dentro del proceso de Faro.** Importar un paquete ejecuta
   su código de módulo; eso no ocurre en el servidor.

**El catálogo es data, no código:** una entrada por librería con los módulos a recorrer. Agregar
FastAPI mañana es agregar una entrada, sin tocar el núcleo.

## 6. Modelo de dominio

- `Fragmento(texto, libreria, version, simbolo, deprecacion)` — todo lo que la cita necesita
  viaja **dentro** del dato. No se puede construir un `Fragmento` sin su procedencia: esa es la
  garantía estructural de la regla nº2.
- `Deprecacion(desde, mensaje, reemplazo)` — extraída de la directiva `.. deprecated::` del docstring.
- `Ambiguo(candidatos)` — la consulta matchea varios símbolos.
- `NoEncontrado(motivo)` — el "no lo tengo" honesto de la regla nº3.

## 7. Herramientas MCP

### 7.1 `listar_versiones(libreria)`

Devuelve la versión **realmente instalada** en el entorno objetivo. Con `FuenteLocal` siempre es
**una sola** — un venv tiene una versión de cada paquete. El nombre queda en plural porque el
puerto `FuenteDeDocs` admite fuentes que sí ofrecen varias (la web sirve 1.4, 2.0 y 2.1 en
simultáneo), y la firma no debe cambiar cuando se enchufe `FuenteWeb`.

```
listar_versiones("sqlalchemy") → ["2.0.36"]
```

Si la librería no está instalada en el entorno objetivo → `NoEncontrado`, nunca lista vacía
ambigua.

### 7.2 `buscar_doc(libreria, version, consulta)`

`version` es **obligatorio, sin default** (regla nº1).

Y aquí ocurre el giro central del diseño: **`version` deja de ser una petición y pasa a ser una
afirmación que Faro verifica.** Si el asistente asume que el proyecto está en 1.4 y pregunta por
la 1.4, Faro responde:

```
No. Tenés instalada la 2.0.36.
```

El parámetro de versión se convierte en una **trampa para alucinaciones**: obliga al modelo a
declarar de qué versión cree que habla, y la realidad del entorno lo desmiente en el acto.

Resolución de la consulta: coincidencia exacta o **por sufijo** (`Session.execute` resuelve
`sqlalchemy.orm.Session.execute`). Sin matching difuso. Si hay varios candidatos → `Ambiguo`,
listándolos. Faro no elige por el usuario.

Salida:

```
sqlalchemy 2.0.36 :: sqlalchemy.orm.Query.get
⚠ DEPRECADO desde 2.0 — usar Session.get
<docstring>
```

Sin URL ni fecha: el artefacto es inmutable y el usuario **puede reproducir la respuesta con un
`python -c`**. Es una forma de verificabilidad más fuerte que un enlace.

### 7.3 `verificar_simbolos(libreria, version, simbolos[])`

Contrasta una lista de símbolos contra el paquete instalado.

```
verificar_simbolos("sqlalchemy", "2.0.36", ["Query.get", "Session.execute"])

  Query.get        ✓ existe   ⚠ DEPRECADO desde 2.0 → usar Session.get
  Session.execute  ✓ existe
```

**Por qué existe esta herramienta.** Los MCP de docs de terceros (Context7 y similares) optimizan
para *cobertura*: miles de librerías, crawleadas de docs públicas. Para lograrlo, la resolución de
versión es necesariamente heurística — en Context7 el parámetro de versión es **opcional** y "se
matchea automáticamente", y el comportamiento ante una versión ausente no está especificado. Su
motor de parseo es privado y no auditable. No están mal hechos: **hicieron el trade-off opuesto, y
la cobertura masiva exige heurísticas que son incompatibles con las tres reglas de arriba.**

`verificar_simbolos` acepta afirmaciones **de cualquier origen** — Context7, un blog, Stack
Overflow, o la propia memoria del modelo — y las contrasta contra el venv del usuario. Ninguna
herramienta de cobertura puede hacer esto, porque ninguna mira el entorno instalado.

Faro deja así de competir en el eje donde pierde (cantidad) y juega en el que gana (certeza).

## 8. Manejo de errores

| Situación | Respuesta |
|---|---|
| Librería no está en el catálogo | `NoEncontrado` + las librerías que sí conoce |
| Versión pedida ≠ versión instalada | `NoEncontrado` + la versión que sí hay. **Jamás** sirve la otra |
| Símbolo no existe en esa versión | `NoEncontrado` |
| Consulta ambigua | `Ambiguo` + candidatos. No elige |
| Entorno objetivo mal configurado | Error explícito. **Nunca** un fallback silencioso al venv de Faro |
| El subproceso falla o el import revienta | Error explícito, distinguible de "no existe" |

La constante: **nunca aproximar en silencio.**

## 9. Testing

**TDD con pytest.** Dos capas, y ambas son necesarias:

**Núcleo contra `FuenteFake`** — sin red, sin subprocesos. Las tres reglas convertidas en asserts:

- pedir la 1.4 teniendo la 2.0.36 → `NoEncontrado`, y se verifica que **no** devolvió la 2.0.36
- `Query.get` en 2.0.36 → existe **y sale marcado como deprecado**, con `Session.get` como reemplazo
- consulta ambigua (`select`) → `Ambiguo` con candidatos, nunca una elección arbitraria
- no se puede construir un `Fragmento` sin librería, versión y símbolo

**Tests de contrato contra un venv real** (`pytest -m contrato`, fuera del ciclo rápido) con
`sqlalchemy==2.0.36` instalado. Verifican que las suposiciones sobre la realidad siguen en pie:
que los docstrings existen, que la directiva `.. deprecated::` está donde creemos.

Esta segunda capa no es opcional. **Los fakes pueden mentir en armonía con nuestras suposiciones
equivocadas**: un fake construido sobre una idea errónea del formato pasa todos los tests mientras
el producto real falla. Los tests de contrato son lo único que ata el diseño a la realidad — el
mismo acto de humildad que fundó este proyecto: verificar en vez de recordar.

## 10. No-objetivos de la v1 (explícitos)

- **No busca en prosa**: ni tutoriales, ni guías de migración. Solo referencia de API. Ante una
  consulta narrativa, Faro dice "no lo tengo" (regla nº3).
- **No sabe de versiones no instaladas.** Puede sugerir instalarlas; nunca las inventa.
- **No cubre librerías que no sean paquetes Python.** `node:sqlite` queda fuera por construcción.
- **No juzga idiomaticidad más allá de la deprecación declarada.** Si un símbolo no está marcado
  con `.. deprecated::`, Faro no opina sobre si es la forma recomendada.

## 11. Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| Cobertura de introspección ~79% de la API documentada | Aceptado. El 21% restante son mayormente símbolos que no resuelven por import; `NoEncontrado` honesto |
| El docstring trae markup RST (`:class:`, `:meth:`) | Limpieza ligera en la capa de presentación, no en el núcleo |
| Importar un paquete ejecuta su código | Aislado en subproceso, fuera del proceso de Faro |
| El tamaño de un docstring de clase puede ser grande | Tope duro de tamaño en la capa de presentación |

## 12. Alcance de la v1

Una librería (SQLAlchemy), tres herramientas (`listar_versiones`, `buscar_doc`,
`verificar_simbolos`), una fuente (`FuenteLocal`), sin caché, sin prosa.

Resuelta de punta a punta, con tests, y conectada a Claude Code por stdio.
