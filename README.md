# udemy-summarizer

Convierte un curso de Udemy (en el que estás inscrito) en un **PDF de estudio** con:

- La estructura completa del curso (secciones y lecciones)
- Las **transcripciones** de cada lección (subtítulos) y el texto de las lecciones tipo artículo
- **Resúmenes por sección generados con IA** (Claude), con conceptos clave, puntos importantes y términos

> Solo para uso personal con cursos en los que estés inscrito.

## Instalación

```bash
pip install -e .
```

Requiere Python 3.10+.

## Cómo obtener tu `access_token` de Udemy

1. Abre [udemy.com](https://www.udemy.com) en tu navegador e inicia sesión.
2. Abre las herramientas de desarrollador (`F12`) → pestaña **Application** (Chrome) o **Storage** (Firefox).
3. En **Cookies → https://www.udemy.com**, busca la cookie `access_token` y copia su valor.
4. Pásalo con `--token` o expórtalo:

```bash
export UDEMY_ACCESS_TOKEN="tu-token-aquí"
```

El token caduca con tu sesión; si recibes un error de autenticación, copia uno nuevo.

## Uso

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
```

El curso se puede indicar por URL completa, slug (`mi-curso`) o ID numérico.

### Opciones

| Opción | Descripción |
|---|---|
| `--token TOKEN` | Cookie `access_token` de Udemy (o `UDEMY_ACCESS_TOKEN`) |
| `--list-courses` | Lista tus cursos inscritos y sale |
| `--locale es` | Idioma preferido de los subtítulos (default: `es`) |
| `--fallback-locale en` | Idioma de respaldo si no hay subtítulos en `--locale` |
| `--output RUTA` | Ruta del PDF (default: `<slug-del-curso>.pdf`) |
| `--no-ai` | Omite los resúmenes con Claude |
| `--model ID` | Modelo de Claude (default: `claude-opus-4-8`) |
| `--max-lectures N` | Limita el número de lecciones (para pruebas) |
| `--dry-run` | Solo muestra la estructura del curso |
| `-v, --verbose` | Salida detallada |

## Resúmenes con IA

Los resúmenes usan la [API de Claude](https://platform.claude.com/) mediante la variable
de entorno `ANTHROPIC_API_KEY`. Si no está definida, la herramienta continúa sin
resúmenes (equivalente a `--no-ai`).

Costo orientativo: un curso típico (~200K tokens de entrada, ~20K de salida con
`claude-opus-4-8`) cuesta alrededor de **$1.50 USD**.

## Desarrollo

```bash
pip install -e ".[dev]"
pytest
```

Los tests no requieren credenciales: la API de Udemy se simula con `responses`
y el cliente de Anthropic con mocks.
