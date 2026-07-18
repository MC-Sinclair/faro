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

Faro no reentrena ni "actualiza" al modelo — eso es imposible desde fuera. Le da
una **herramienta** para ir a buscar el texto real de la documentación cuando la
respuesta lo necesita. La diferencia con su memoria es la que hay entre citar un libro
de memoria y tenerlo abierto en la mano.

## Por qué construirlo (y cuándo NO)

Sé honesto contigo mismo antes de empezar:

- **Ya existen** servidores MCP de documentación de terceros. Si lo único que querés
  es la capacidad, instalá uno con `/plugin` y listo — no construyas.
- **Construí Faro si** querés: (a) control total sobre *qué fuentes* se consultan
  y con qué versión (evitar que te sirvan la doc de una versión que no es la tuya),
  (b) un proyecto de aprendizaje real sobre el protocolo MCP, o (c) una herramienta a
  medida de tu stack, sin depender de un tercero cuya calidad de fuentes no controlás.

Esta decisión es la primera de la mesa de apuestas. No la saltes.

## Principio rector: verificabilidad, no confianza ciega

Este es el hilo que debe atravesar todo el diseño:

> Un MCP de docs no vuelve al asistente infalible. Le da de dónde agarrarse.

Un buen servidor cita la versión y la URL de origen, así el humano puede verificar.
Un mal servidor —o uno que trae la doc de la versión equivocada— hace que el asistente
**yerre con más confianza todavía**. Por eso Faro debe:

1. **Fijar versión siempre.** Nunca devolver "la última" implícita; que el consumidor
   la pida explícita.
2. **Citar la fuente en cada respuesta** (para Faro: la versión exacta del paquete
   instalado que se leyó — ver "Origen" abajo).
3. **Fallar honestamente.** Si no tiene la versión pedida, decir "no la tengo",
   nunca aproximar en silencio con otra. Un `null` honesto vale más que un fragmento
   plausible pero de otra versión.

## Origen: de la semilla a la v1 construida

Este README arrancó como una semilla de brainstorming: una lista de decisiones abiertas
(¿qué librería objetivo? ¿fetch web o paquete instalado? ¿Python o Node?) para resolver
antes de escribir código. Esas decisiones ya se cerraron y la v1 ya está construida y en
uso — el registro completo de *por qué* se decidió cada cosa (incluido el giro de
"scraping de la web" a "introspección del paquete instalado", y el error de memoria que
terminó fundando el caso de prueba central del proyecto) vive en `CLAUDE.md`, no acá.

En resumen, lo que se decidió: SQLAlchemy 2.x como librería objetivo (de una lista que
incluía FastAPI, la API de Claude y `node:sqlite`), Python + `uv` como runtime, y como
fuente de verdad **el paquete realmente instalado** en el venv del proyecto del usuario
— no la web, sin caché, siguiendo la misma Dependency Rule que separa el núcleo
(`resolver.py`, `dominio.py`, `parseo.py`, `catalogo.py`) del transporte MCP y de la
extracción por subproceso (`FuenteLocal` + `extractor.py`).

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

Funciona con **cualquier librería instalada**, no solo SQLAlchemy: SQLAlchemy
tiene una lista curada de módulos (afinada para no traer ruido de dialectos
internos o utilidades de testing); cualquier otra librería descubre sus
submódulos automáticamente.

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
