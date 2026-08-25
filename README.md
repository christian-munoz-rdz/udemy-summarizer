# udemy-summarizer

Convierte un curso de **Udemy** o **Coursera** (en el que estás inscrito) en un **PDF de estudio** con:

- La estructura completa del curso (secciones y lecciones)
- Las **transcripciones** de cada lección (subtítulos) y el texto de las lecciones tipo artículo/lectura
- **Resúmenes por sección generados con IA** (Claude), con conceptos clave, puntos importantes y términos

> Solo para uso personal con cursos en los que estés inscrito.

Requiere [uv](https://docs.astral.sh/uv/) y Python 3.10+.

## Instalación

Si aún no tienes uv:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

En la carpeta del proyecto:

```bash
cd udemy-summarizer
uv sync
cp .env.example .env   # Windows: copy .env.example .env
```

`uv sync` crea `.venv`, instala el paquete y las dependencias de desarrollo (el archivo `uv.lock` fija las versiones).

Comprueba que el comando funciona:

```bash
uv run udemy-summarizer --version
```

No hace falta activar el entorno: `uv run` usa `.venv` por ti.

Para la interfaz gráfica:

```bash
uv run udemy-summarizer-gui
```

## Autenticación

Las credenciales se leen del archivo `.env` en el directorio desde el que ejecutas el comando. Copia la plantilla (paso de instalación) y rellena los valores.

`--token` en la CLI pisa el valor de `.env`. Las variables ya definidas en el entorno del sistema también tienen prioridad sobre el archivo.

### Udemy: `access_token`

1. Abre [udemy.com](https://www.udemy.com) en tu navegador e inicia sesión.
2. Abre las herramientas de desarrollador (`F12`) → pestaña **Application** (Chrome) o **Storage** (Firefox).
3. En **Cookies → https://www.udemy.com**, busca la cookie `access_token` y copia su valor.
4. Pégalo en `.env`:

```bash
UDEMY_ACCESS_TOKEN="tu-token-aquí"
```

El token caduca con tu sesión; si recibes un error de autenticación, copia uno nuevo.

### Coursera: cookie `CAUTH`

1. Abre [coursera.org](https://www.coursera.org) e inicia sesión.
2. Abre las herramientas de desarrollador (`F12`) → **Application** → **Cookies → https://www.coursera.org**.
3. Busca la cookie **`CAUTH`** y copia su valor.
4. Pégalo en `.env`:

```bash
COURSERA_CAUTH="tu-cauth-aquí"
```

La cookie caduca con tu sesión; renueva el valor si recibes un error de autenticación.

## Uso

Ejecuta siempre desde la carpeta del proyecto (donde está `.env`).

### Interfaz gráfica (PyQt6)

La GUI expone las mismas opciones que la CLI:

- Plataforma (Udemy / Coursera) y token opcional
- Curso (URL, slug o ID) con listado de cursos inscritos
- Idioma de subtítulos, inglés, dry-run, verbose y límite de lecciones
- Resúmenes IA (modelo y `--no-ai`)
- **Carpeta de destino** del PDF y nombre de archivo opcional

```bash
uv run udemy-summarizer-gui
```

Usa **Examinar…** para elegir la carpeta donde se guardará el PDF. Si dejas el nombre vacío, se genera automáticamente a partir del título del curso.

### CLI — Udemy (por defecto)

```bash
# Listar tus cursos inscritos
uv run udemy-summarizer --list-courses

# Ver la estructura de un curso y la disponibilidad de subtítulos (no descarga nada)
uv run udemy-summarizer https://www.udemy.com/course/mi-curso/ --dry-run

# Generar el PDF completo (transcripciones + resúmenes IA)
# Requiere ANTHROPIC_API_KEY en .env
uv run udemy-summarizer mi-curso

# Sin resúmenes IA (no requiere ANTHROPIC_API_KEY)
uv run udemy-summarizer mi-curso --no-ai

# Prueba rápida con solo 3 lecciones
uv run udemy-summarizer mi-curso --no-ai --max-lectures 3

# Transcripciones en inglés
uv run udemy-summarizer mi-curso --no-ai --english
```

El curso se puede indicar por URL completa, slug (`mi-curso`) o ID numérico.

### CLI — Coursera

```bash
# Listar cursos inscritos
uv run udemy-summarizer --platform coursera --list-courses

# Ver estructura y subtítulos disponibles
uv run udemy-summarizer --platform coursera machine-learning --dry-run

# Generar PDF
uv run udemy-summarizer --platform coursera machine-learning --no-ai

# Transcripciones en inglés
uv run udemy-summarizer --platform coursera machine-learning --no-ai --english
```

Indica el curso por URL (`https://www.coursera.org/learn/machine-learning`) o slug (`machine-learning`).

### Opciones CLI

| Opción | Descripción |
|---|---|
| `--platform {udemy,coursera}` | Plataforma del curso (default: `udemy`) |
| `--token TOKEN` | Credencial de la plataforma; pisa `UDEMY_ACCESS_TOKEN` o `COURSERA_CAUTH` de `.env` |
| `--list-courses` | Lista tus cursos inscritos y sale |
| `--locale es` | Idioma preferido de los subtítulos (default: `es`; usa `en` para inglés) |
| `--english` | Atajo para transcripciones en inglés (`--locale en --fallback-locale en`) |
| `--fallback-locale en` | Idioma de respaldo si no hay subtítulos en `--locale` (default: `en`) |
| `--output RUTA` | Ruta del PDF (default: `<slug-del-curso>.pdf`) |
| `--no-ai` | Omite los resúmenes con Claude |
| `--model ID` | Modelo de Claude (default: `claude-opus-4-8`) |
| `--max-lectures N` | Limita el número de lecciones (para pruebas) |
| `--dry-run` | Solo muestra la estructura del curso |
| `-v, --verbose` | Salida detallada |

## Limitaciones de Coursera

- Solo cursos individuales en `/learn/slug` (no especializaciones ni cursos legacy).
- Quizzes, exámenes, tareas calificadas y notebooks Jupyter no se incluyen en el PDF.
- Algunos cursos no tienen subtítulos en el idioma solicitado.

## Resúmenes con IA

Los resúmenes usan la [API de Claude](https://platform.claude.com/) mediante `ANTHROPIC_API_KEY`
en `.env`. Si no está definida, la herramienta continúa sin resúmenes (equivalente a `--no-ai`).

Cada resumen incluye conceptos clave, puntos importantes y términos; en cursos
técnicos también **snippets de código** (renderizados con fuente monoespaciada) y
**diagramas Mermaid** cuando ayudan a visualizar un flujo o arquitectura. Los
diagramas se renderizan a imagen mediante el servicio [mermaid.ink](https://mermaid.ink);
si no hay conexión o el renderizado falla, el PDF incluye el código del diagrama
como texto.

Costo orientativo: un curso típico (~200K tokens de entrada, ~20K de salida con
`claude-opus-4-8`) cuesta alrededor de **$1.50 USD**.

## Troubleshooting

### `uv: command not found`

uv no está en el `PATH`. Instálalo (sección [Instalación](#instalación)) y abre una terminal nueva.

### `Failed to spawn: 'udemy-summarizer'` / comando no encontrado

El paquete no está instalado en `.venv`. Desde la carpeta del proyecto:

```bash
uv sync
uv run udemy-summarizer --version
```

Usa `uv run udemy-summarizer ...`; no hace falta (ni se recomienda) invocar el comando a pelo.

### Actualicé dependencias o `pyproject.toml`

Vuelve a sincronizar el entorno:

```bash
uv sync
```

Los cambios en el código fuente se recogen al instante (instalación editable).

### No encuentra las credenciales

El CLI carga `.env` del directorio de trabajo actual. Ejecuta el comando desde la carpeta del proyecto (donde copiaste `.env.example` a `.env`) y comprueba que las variables no estén vacías.

También puedes pasar la credencial directamente: `--token "..."`.

### Error de autenticación (401 / 403)

La cookie `access_token` (Udemy) o `CAUTH` (Coursera) caducó. Copia un valor nuevo desde las DevTools del navegador y actualízalo en `.env`.

## Desarrollo

```bash
uv sync
uv run pytest
```

`uv sync` incluye el grupo `dev` (`pytest`, `responses`). Los tests no requieren credenciales: las APIs de Udemy y Coursera se simulan con `responses` y el cliente de Anthropic con mocks.
