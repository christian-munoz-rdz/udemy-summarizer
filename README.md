# udemy-summarizer

Convierte un curso de **Udemy** o **Coursera** (en el que estás inscrito) en un **PDF de estudio** con:

- La estructura completa del curso (secciones y lecciones)
- Las **transcripciones** de cada lección (subtítulos) y el texto de las lecciones tipo artículo/lectura
- **Resúmenes por sección generados con IA** (Claude), con conceptos clave, puntos importantes y términos

> Solo para uso personal con cursos en los que estés inscrito.

## Instalación

Recomendado: usar un entorno virtual para aislar las dependencias.

```bash
cd udemy-summarizer
python3 -m venv .venv
source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install .
```

Comprueba que el comando quedó disponible:

```bash
which udemy-summarizer   # debe apuntar a .venv/bin/udemy-summarizer
udemy-summarizer --version
```

Requiere Python 3.10+.

Para desarrollo (tests):

```bash
pip install ".[dev]"
pytest
```

> Si `pip install -e .` falla con un error sobre `build_editable`, usa `pip install .` (sin `-e`).

## Autenticación

### Udemy: `access_token`

1. Abre [udemy.com](https://www.udemy.com) en tu navegador e inicia sesión.
2. Abre las herramientas de desarrollador (`F12`) → pestaña **Application** (Chrome) o **Storage** (Firefox).
3. En **Cookies → https://www.udemy.com**, busca la cookie `access_token` y copia su valor.
4. Pásalo con `--token` o expórtalo:

```bash
export UDEMY_ACCESS_TOKEN="tu-token-aquí"
```

El token caduca con tu sesión; si recibes un error de autenticación, copia uno nuevo.

### Coursera: cookie `CAUTH`

1. Abre [coursera.org](https://www.coursera.org) e inicia sesión.
2. Abre las herramientas de desarrollador (`F12`) → **Application** → **Cookies → https://www.coursera.org**.
3. Busca la cookie **`CAUTH`** y copia su valor.
4. Pásalo con `--token` o expórtalo:

```bash
export COURsera_CAUTH="tu-cauth-aquí"
```

La cookie caduca con tu sesión; renueva el valor si recibes un error de autenticación.

## Uso

### Udemy (por defecto)

```bash
# Listar tus cursos inscritos
udemy-summarizer --list-courses

# Ver la estructura de un curso y la disponibilidad de subtítulos (no descarga nada)
udemy-summarizer https://www.udemy.com/course/mi-curso/ --dry-run

# Generar el PDF completo (transcripciones + resúmenes IA)
export ANTHROPIC_API_KEY="sk-ant-..."
udemy-summarizer mi-curso

# Sin resúmenes IA (no requiere ANTHROPIC_API_KEY)
udemy-summarizer mi-curso --no-ai

# Prueba rápida con solo 3 lecciones
udemy-summarizer mi-curso --no-ai --max-lectures 3

# Transcripciones en inglés
udemy-summarizer mi-curso --no-ai --english
```

El curso se puede indicar por URL completa, slug (`mi-curso`) o ID numérico.

### Coursera

```bash
# Listar cursos inscritos
udemy-summarizer --platform coursera --list-courses

# Ver estructura y subtítulos disponibles
udemy-summarizer --platform coursera machine-learning --dry-run

# Generar PDF
udemy-summarizer --platform coursera machine-learning --no-ai

# Transcripciones en inglés
udemy-summarizer --platform coursera machine-learning --no-ai --english
```

Indica el curso por URL (`https://www.coursera.org/learn/machine-learning`) o slug (`machine-learning`).

### Opciones

| Opción | Descripción |
|---|---|
| `--platform {udemy,coursera}` | Plataforma del curso (default: `udemy`) |
| `--token TOKEN` | Credencial de la plataforma (`UDEMY_ACCESS_TOKEN` o `COURsera_CAUTH`) |
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

Los resúmenes usan la [API de Claude](https://platform.claude.com/) mediante la variable
de entorno `ANTHROPIC_API_KEY`. Si no está definida, la herramienta continúa sin
resúmenes (equivalente a `--no-ai`).

Cada resumen incluye conceptos clave, puntos importantes y términos; en cursos
técnicos también **snippets de código** (renderizados con fuente monoespaciada) y
**diagramas Mermaid** cuando ayudan a visualizar un flujo o arquitectura. Los
diagramas se renderizan a imagen mediante el servicio [mermaid.ink](https://mermaid.ink);
si no hay conexión o el renderizado falla, el PDF incluye el código del diagrama
como texto.

Costo orientativo: un curso típico (~200K tokens de entrada, ~20K de salida con
`claude-opus-4-8`) cuesta alrededor de **$1.50 USD**.

## Troubleshooting

### `zsh: command not found: udemy-summarizer`

El comando no existe hasta que instalas el paquete **y** activas el entorno virtual donde lo instalaste.

```bash
cd udemy-summarizer
source .venv/bin/activate
pip install .
udemy-summarizer --version
```

Si no has creado el venv aún:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

Cada terminal nueva requiere `source .venv/bin/activate` antes de usar el comando.

### `pip install -e .` falla (error `build_editable`)

Algunas versiones de setuptools no soportan instalación editable en este proyecto. Instala en modo normal:

```bash
pip install .
```

Funciona igual; solo que si editas el código tendrás que reinstalar con `pip install .` para ver los cambios.

### Actualicé el código pero no veo los cambios

Reinstala dentro del venv activo:

```bash
source .venv/bin/activate
pip install .
```

### Las variables de entorno no se reconocen

`export UDEMY_ACCESS_TOKEN=...` y `export COURsera_CAUTH=...` solo viven en la terminal actual. Si abres otra pestaña o reinicias el shell, expórtalas de nuevo (con el venv activado):

```bash
source .venv/bin/activate
export COURsera_CAUTH="..."
udemy-summarizer --platform coursera --list-courses
```

También puedes pasar la credencial directamente: `--token "..."`.

### Error de autenticación (401 / 403)

La cookie `access_token` (Udemy) o `CAUTH` (Coursera) caducó. Copia un valor nuevo desde las DevTools del navegador y vuelve a exportarlo o usa `--token`.

## Desarrollo

```bash
source .venv/bin/activate
pip install ".[dev]"
pytest
```

Los tests no requieren credenciales: las APIs de Udemy y Coursera se simulan con `responses`
y el cliente de Anthropic con mocks.
