# ETL Suite Agéntica

Plataforma unificada de ejecución, administración y observabilidad de los ETLs de Evoltis.

No es un monorepo de scripts: es una **capa de ejecución controlada** que envuelve ETLs legacy
como procesos invocables, con sandbox aislado por corrida, evidencia forense (hash de inputs,
stdout/stderr, exit code, artefactos detectados), locking por período y promoción durable del
estado persistente.

---

## Índice

- [Cómo levantar el proyecto](#cómo-levantar-el-proyecto)
- [Cómo ejecutar un ETL](#cómo-ejecutar-un-etl)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Clientes y ETLs disponibles](#clientes-y-etls-disponibles)
- [Conceptos clave](#conceptos-clave)
- [Tests](#tests)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Documentación adicional](#documentación-adicional)

---

## Cómo levantar el proyecto

### Requisitos

- Python >= 3.12
- Node 18+ (sólo para la UI web)

### Instalación

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[test,etl,api]"
```

> El extra `etl` instala `pandas` y `openpyxl`, que usan los ETLs de todos los clientes.
> `naranjax` se mantiene como alias del mismo conjunto por compatibilidad con entornos
> existentes. El extra `api` instala FastAPI, Uvicorn y python-multipart.

### Con Docker

```bash
docker compose up                  # API en http://localhost:8000
docker compose --profile dev up    # API + frontend dev en http://localhost:5173
```

El directorio `var/` (corridas, estado, uploads) se monta como volumen desde el host.

### API + UI web

```bash
# Terminal 1 — backend
uvicorn platform_api.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev        # http://localhost:5173
```

El CORS del backend está abierto sólo a `http://localhost:5173` y `http://127.0.0.1:5173`.

---

## Cómo ejecutar un ETL

### Desde la CLI

```bash
python -m orchestrator.run \
  --etl naranjax.ma.chat.daily \
  --fecha 20260806 \
  --base ./inputs/base_mensual.xlsx \
  --input planes=./inputs/planes.xlsx \
  --input pagos=./inputs/pagos.csv
```

Cuando el día no tiene archivo de PLANES, se declara explícitamente con un parámetro:

```bash
python -m orchestrator.run \
  --etl naranjax.ma.chat.daily \
  --fecha 20260806 \
  --base ./inputs/base_mensual.xlsx \
  --param no_planes_today
```

Toda entrada adicional a `base` se pasa con `--input ROL=RUTA`, y los flags que el
manifiesto declara, con `--param NOMBRE[=VALOR]`:

```bash
python -m orchestrator.run \
  --etl petersen.gestiones \
  --fecha 20260806 \
  --base ./inputs/base.csv \
  --input clientes=./inputs/clientes.csv \
  --input excluidos=./inputs/excluidos.csv
```

### Códigos de salida de la CLI

| Código | Significado |
|--------|-------------|
| `0` | La corrida terminó bien (`succeeded`) |
| `1` | La corrida falló (`failed` / `timed_out`) |
| `2` | La corrida quedó bloqueada (`blocked`): validación, lock tomado, snapshot ya existente, recovery pendiente |

### Desde la API

```
GET  /api/catalog                          Catálogo de ETLs con inputs, outputs y estado
POST /api/runs                             Dispara una corrida (multipart con los archivos)
GET  /api/runs                             Lista corridas, con filtros y paginado
GET  /api/runs/{run_id}                    Detalle de una corrida
GET  /api/runs/{run_id}/artifacts.zip      Descarga todos los artefactos + run.json
GET  /api/runs/{run_id}/artifacts/{rol}    Descarga un artefacto puntual
GET  /api/schedule                         Deadlines de hoy + corridas huérfanas recuperadas
POST /api/runs/{run_id}/actions/notify_dev Notifica a desarrollo (webhook + registro durable)
POST /api/runs/{run_id}/actions/free_lock  Libera un lock huérfano (rechaza si hay corrida viva)
```

### Configuración de la API (variables de entorno)

| Variable | Default | Efecto |
|---|---|---|
| `ETL_CONSOLE_TOKEN` | vacío (sin auth) | Si está seteada, todo `/api/*` exige `Authorization: Bearer <token>` o `X-Api-Token`. La consola lo toma de `localStorage("etl_token")`. |
| `ETL_RETENTION_DAYS` | `30` | Al arrancar borra corridas terminales y uploads más viejos que N días (contienen PII). `0` desactiva. |
| `ETL_NOTIFY_WEBHOOK` | vacío | URL a la que `notify_dev` postea el JSON de la notificación (Slack/Teams/n8n). Siempre queda registro en `var/notifications.jsonl`. |
| `ETL_MAX_CONCURRENT_RUNS` | `2` | Tamaño del pool de ejecución (hilos no-daemon: las corridas en curso terminan antes de apagar). |

Al arrancar, la API además marca como `failed`/`orphaned` las corridas que quedaron vivas
de un proceso anterior, y sirve el listado desde un índice SQLite (`var/index.sqlite`)
en vez de escanear el filesystem.

### Desde un agente (MCP)

```bash
pip install -e ".[mcp]"
```

```json
{"command": "python", "args": ["-m", "platform_mcp.server"],
 "env": {"ETL_API_URL": "http://localhost:8000", "ETL_CONSOLE_TOKEN": "..."}}
```

Herramientas: `list_etls`, `describe_etl`, `run_etl`, `get_run`, `download_artifact`.
Para que un agente dé de alta un cliente nuevo: copiar `etls/_template/` y seguir
`docs/GUIA_NUEVO_CLIENTE.md`.

---

## Estructura del repositorio

```
etl-suite-agentica/
├── etl_core/                 Contrato de adapter: Protocol, excepciones, SubprocessAdapter
├── orchestrator/             Núcleo: catálogo, servicio, runner, sandbox, estado, CLI
├── etls/<cliente>/           Paquete autocontenido por cliente:
│   ├── manifest.yaml         declaración del catálogo
│   ├── adapter.py / *.py     adapters del cliente
│   ├── job.py                CLI puente al legacy (si hace falta)
│   ├── legacy/               proyecto ETL original, invocado sin modificar
│   ├── tests/                e2e + unit del cliente
│   └── README.md             entradas, salidas, deadline, reglas, contacto
├── platform_api/             API REST (FastAPI) sobre el orquestador
├── frontend/                 Consola web (React + Vite + TypeScript)
├── tests/                    unit del núcleo + API + soporte compartido
├── openspec/                 Especificaciones y propuestas de cambio
└── docs/                     Arquitectura, ADRs y guías
```

**Agregar un cliente = agregar una carpeta bajo `etls/`.** El catálogo descubre
`etls/*/manifest.yaml` y resuelve el adapter por import (`modulo:Clase`); no se toca
ningún archivo del núcleo.

### Qué hace cada módulo del núcleo

| Archivo | Responsabilidad |
|---|---|
| `orchestrator/catalog.py` | Carga y valida los YAML de `registry/`. Rechaza rutas fuera del workspace, roles duplicados, formatos de fecha desconocidos y ETLs marcados ejecutables sin metadata completa. |
| `orchestrator/models.py` | Contratos de datos: `ETLDefinition`, `RunRequest`, `RunResult`, `FileEvidence`, y los enums de estado. Todo inmutable (`frozen=True`). |
| `orchestrator/service.py` | Orquesta la corrida completa y escribe `run.json` en cada transición. Es la máquina de estados. |
| `orchestrator/runner.py` | Ejecuta el subprocess con `cwd` controlado, timeout, drenado de stdout/stderr en hilos y escalada terminate → kill. |
| `orchestrator/run_store.py` | Crea el sandbox, escribe metadata de forma durable (tmp + `os.replace` + fsync) y gestiona el lock por `etl_id/YYYYMM`. |
| `orchestrator/state_store.py` | Promoción durable del estado persistente: snapshot del día + estado corriente del mes, con marcador de recovery si la promoción queda a medias. |
| `orchestrator/file_manager.py` | Copia inputs al sandbox validando extensión, e inventaría el directorio de salida antes y después. |
| `orchestrator/logging_utils.py` | Persiste logs y aplica el `Redactor` sobre secretos y rutas absolutas. |
| `orchestrator/run.py` | CLI y registro de adapters. |

---

## Clientes y ETLs disponibles

Cada cliente vive en `etls/<cliente>/` con su `manifest.yaml` y su `README.md`. Ejecutá
`GET /api/catalog` o abrí el manifest para ver el listado vigente, sus entradas requeridas
y sus patrones de salida.

| Cliente | Paquete | Estado general |
|---|---|---|
| Naranja X | `etls/naranjax/` | 7 ETLs operativos (MA Chat, MA Voz, MT Voz, PCT) |
| Bancor | `etls/bancor/` | Base diaria operativa; resultados, carga masiva y cupones pendientes |
| Petersen | `etls/petersen/` | Gestiones operativo; Retell pendiente |
| EPEC | `etls/epec/` | Base operativa; tipificaciones Retell pendientes |
| Frávega | `etls/fravega/` | Base operativa; resultados Retell pendientes |
| Claro Uruguay | `etls/clarouy/` | Base operativa; encuestas Retell pendientes |
| Encuesta CX | `etls/encuestacx/` | Base operativa |
| Social Learning | `etls/sociallearning/` | Argentina y Chile operativos |

Los ETLs con `executable: false` aparecen en el catálogo pero no se pueden disparar. El motivo
legible está en `platform_api/catalog_meta.py` (`INERT_REASONS`). Casi todos esperan
credenciales de la API de Retell.ai.

---

## Conceptos clave

### Sandbox por corrida

Cada ejecución vive aislada en su propia carpeta. Nada se escribe fuera de ahí, salvo la
promoción de estado al final:

```
var/runs/<etl_id>/<timestamp>_<uuid>/
├── input/       Copia de los archivos de entrada, con hash registrado
├── output/      Artefactos generados por el ETL legacy
├── logs/        stdout.log, stderr.log y logs propios del legacy
├── state/       Estado persistente puesto a disposición del legacy
├── processed/   Archivos que el legacy marca como procesados
└── run.json     Metadata completa de la corrida
```

### Ciclo de vida de una corrida

```
preparing → running → succeeded
                    → failed       (exit code no permitido, spawn fallido, postcondición)
                    → timed_out
          → blocked                (validación, lock tomado, snapshot existente, recovery)
```

### Lock por período

Antes de ejecutar, el servicio toma un lock en `var/state/<etl_id>/<YYYYMM>/.lock`. Impide dos
corridas simultáneas del mismo ETL sobre el mismo mes. El lock guarda quién lo tomó (`run_id`,
pid, host, token) para poder auditar un lock huérfano. Se libera con verificación de propiedad:
si el token no coincide, no se borra.

### Estado persistente y promoción

Los ETLs con estado (por ejemplo Naranja X MA Chat) leen y escriben un archivo mensual acumulado.
El flujo es: se copia el estado corriente al sandbox → el legacy lo modifica → si la corrida
tuvo éxito, se promueven dos archivos de forma durable:

- `estado_YYYYMMDD.csv` — snapshot inmutable del día
- `estado_YYYYMM.csv` — estado corriente del mes

Si el snapshot se publica pero el estado corriente no, queda un `recovery.json` en la carpeta de
linaje y **todas las corridas siguientes de ese ETL/mes quedan bloqueadas** hasta que alguien
resuelva la inconsistencia a mano. Es deliberado: preferimos frenar antes que corromper.

### Postcondiciones de salida

El adapter no confía en el exit code. Después de ejecutar compara el inventario del directorio
`output/` antes y después, y para cada salida declarada en el YAML valida que exista exactamente
un archivo que matchee el glob, que tenga la fecha esperada en el nombre y que no sea idéntico a
uno preexistente. Si algo no cumple, la corrida falla aunque el legacy haya devuelto `0`.

### Redacción de secretos

Todo lo que se escribe en `run.json` y en los logs pasa por el `Redactor`: se enmascaran los
valores de variables de entorno declaradas y las rutas absolutas del host.

> **Ojo:** el `Redactor` no enmascara datos personales del negocio (DNI, teléfonos, montos).
> Los artefactos y logs pueden contener PII. Tratá `var/` como material sensible.

---

## Tests

```bash
pytest                    # todo
pytest tests/orchestrator # unit del núcleo
pytest tests/adapters     # unit de adapters
pytest tests/api          # API
pytest tests/e2e          # end-to-end por ETL (los más valiosos ante un refactor)
```

Los 13 tests de `tests/e2e/` son la red de seguridad del proyecto: cubren un ETL cada uno de punta
a punta. **Antes de cualquier refactor del núcleo, corrélos; después del refactor, tienen que
seguir pasando sin modificarse.** Si un refactor obliga a tocar un e2e, eso es señal de que
cambiaste comportamiento observable, no sólo estructura.

---

## Limitaciones conocidas

Son deudas asumidas, no bugs sorpresa. Están priorizadas en `docs/ADR-001-nucleo-hexagonal.md`.

1. **Sólo se acepta la fecha de hoy.** Los adapters y la API rechazan cualquier `business_date`
   distinta de `date.today()`, porque los ETLs legacy estampan la fecha del sistema en los nombres
   de salida. No hay reproceso ni backfill.
2. **`SubprocessAdapter` es compartido por 10 ETLs de 6 clientes.** Ya tiene nombre honesto y
   vive en `etl_core`, pero un cambio ahí sigue exigiendo correr los 13 e2e completos.
3. **La autenticación es un token único compartido** (`ETL_CONSOLE_TOKEN`), sin usuarios ni
   roles. Los links de descarga de artefactos no adjuntan el token (usá la API con header).
4. **El scheduling es informativo:** `/api/schedule` cruza deadlines declarados con las
   corridas del día, pero nadie dispara ETLs automáticamente todavía.

---

## Documentación adicional

- `docs/ARQUITECTURA.md` — capas, flujo de una corrida y contrato de adapter
- `docs/ADR-001-nucleo-hexagonal.md` — decisión de arquitectura y plan de migración
- `docs/GUIA_NUEVO_CLIENTE.md` — cómo agregar un cliente paso a paso
- `01_objetivo_proyecto_etl_unificador.md` — objetivo original del proyecto (histórico)
- `openspec/` — propuestas de cambio y especificaciones por capability
