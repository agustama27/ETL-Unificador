# Comandos

Tareas de `Taskfile.yml` y entrypoints del repositorio. Fuente única: si un comando cambia,
se cambia acá, no en el `README.md` ni en el `AGENTS.md`.

## Requisitos

| Herramienta | Para qué | Obligatoria |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | dependencias, entorno y ejecución (ADR-ARC-003) | sí |
| [Task](https://taskfile.dev) | runner de las tareas de abajo | sí |
| `sonar-scanner` | análisis local de SonarQube | no |
| `helm` | validar y empaquetar el chart | sí para desplegar |
| `docker`, `aws`, `yq` | construir y publicar en ECR | sí para desplegar |

Sin Task, cada tarea se puede correr a mano con el `uv run ...` equivalente que figura en
`Taskfile.yml`.

## Tareas

| Tarea | Qué hace |
|---|---|
| `task sync` | Sincroniza el entorno desde `uv.lock`. Es dependencia de casi todas las demás. |
| `task validate` | Compila las fuentes propias. Detecta errores de sintaxis e import sin correr tests. |
| `task lint` | `ruff check` sobre las fuentes propias. |
| `task test` | Suite completa. |
| `task test:parity` | Solo la paridad byte a byte contra los repos upstream, con `-rs`. |
| `task coverage` | Suite con cobertura y `coverage.xml` para SonarQube. |
| `task sonar` | Análisis de SonarQube local. Requiere `sonar-scanner` en el PATH. |
| `task run` | Levanta la API en `0.0.0.0:8000`. |
| `task check` | `validate` + `lint` + `test` + `helm:lint`. Lo que tiene que estar verde antes de abrir un PR. |
| `task helm:lint` / `helm:template` | Valida y renderiza el chart de `deploy/package`. |
| `task docker:build` / `docker:push` | Imagen del servicio. El contexto de build es la raíz. |
| `task publish` | Login en ECR + build + push de imagen y chart. Toma `VERSION` y `ENV`. |

## Estado esperado de la suite

`412 passed, 1 xfailed`. **Cero skips.**

Un skip no es un pase. Los dos lugares donde un skip es fácil de confundir con verde:

- `test/integration/uat_upstream/` se saltea entero si los repos upstream no están en el Escritorio.
  Ver [../explanation/paridad-upstream.md](../explanation/paridad-upstream.md) para qué cubre
  y qué no.
- Los tests que usan `pytest.importorskip` se saltean si falta una dependencia opcional.
  Todas están declaradas en `pyproject.toml`; si alguna se saltea, el entorno está
  desincronizado del lock: corré `task sync`.

El `xfailed` es `test_la_salida_sin_filtros_activa_la_campania_preventa`, que documenta un
hueco del upstream de Bancor. Es `strict`: si pasa a XPASS, el upstream lo arregló y hay que
sacar el marker.

## Dependencias pineadas a versión exacta

Las del camino de datos van pineadas, no a rango:

| Paquete | Versión | Por qué |
|---|---|---|
| `pandas` | 2.3.3 | formato numérico y de fecha de toda salida CSV |
| `numpy` | 2.4.6 | backend numérico de pandas. 2.4.0 está *yanked* en PyPI |
| `openpyxl` | 3.1.5 | lectura/escritura de `.xlsx` |
| `xlrd` | 2.0.2 | lectura de `.xls` (Alvarez) |
| `pypdf` | 6.9.2 | extracción de PDF (Alvarez) |
| `holidays` | 0.99 | días hábiles de CartaSur: un cambio mueve fechas de salida |

Subirlas es un cambio deliberado con UAT contra los repos upstream, no un `uv lock --upgrade`.
El motivo está en [../explanation/paridad-upstream.md](../explanation/paridad-upstream.md).
