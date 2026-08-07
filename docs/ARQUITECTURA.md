# Arquitectura — ETL Suite Agéntica

Documento de referencia para quien va a modificar el sistema. Describe **el estado actual**,
no el objetivo. La arquitectura objetivo y su justificación están en
`docs/ADR-001-nucleo-hexagonal.md`.

---

## 1. Principio rector

Los ETLs existentes se tratan como **legacy jobs invocables**, no como código a refactorizar.
La plataforma los ejecuta por subprocess, captura su salida, detecta sus artefactos y devuelve
un resultado estructurado.

La consecuencia práctica: **la lógica de negocio del cliente nunca vive en el núcleo**. Reglas de
quita de Bancor, filtros de módulos, códigos PCT, scope de cajones de Naranja X, consolidación por
DNI, prioridad planes > pagos > API, estructura de CRM, reglas de exclusión: todo eso queda dentro
del proyecto legacy del cliente. El núcleo sólo sabe de archivos, comandos, estados y evidencia.

---

## 2. Las cuatro capas

```
┌──────────────────────────────────────────────────────────────┐
│  Interfaces                                                  │
│  CLI · API REST (FastAPI) · UI web (React) · MCP (stdio)     │
└──────────────────────────┬───────────────────────────────────┘
                           │  RunRequest / RunResult
┌──────────────────────────▼───────────────────────────────────┐
│  Núcleo orquestador                                          │
│  Catálogo · Servicio · Runner · Sandbox · Estado · Locks     │
│  No conoce ningún cliente. Sólo archivos, procesos, estados. │
│  Importa el contrato desde etl_core/contracts.py.            │
└──────────────────────────┬───────────────────────────────────┘
                           │  Protocol ETLAdapter (etl_core)
┌──────────────────────────▼───────────────────────────────────┐
│  Paquetes de cliente (etls/<cliente>/)                       │
│  manifest.yaml · adapter · job.py · legacy/ · tests · README │
└──────────────────────────┬───────────────────────────────────┘
                           │  subprocess
┌──────────────────────────▼───────────────────────────────────┐
│  Proyectos ETL legacy (etls/<cliente>/legacy/)               │
│  Reglas de negocio del cliente. No se modifican.             │
└──────────────────────────────────────────────────────────────┘
```

El **catálogo declarativo** (`etls/*/manifest.yaml`) atraviesa las cuatro capas: define qué
ETLs existen, qué comando ejecutan, qué entradas piden y qué salidas prometen. El campo
`adapter` es una ruta de importación `modulo:Clase` que el catálogo resuelve dinámicamente,
validando que la clase satisfaga el Protocol antes de aceptar el ETL como ejecutable.
Agregar un cliente = agregar una carpeta; ningún archivo del núcleo se toca.

Sobre el núcleo, `platform_api/` agrega la capa operativa: índice SQLite de corridas
(`var/index.sqlite` — `run.json` sigue siendo la fuente de verdad), recuperación de
corridas huérfanas al arrancar (código `orphaned`), retención de evidencia con PII,
autenticación por token fail-closed y notificaciones por webhook. `platform_mcp/` expone
las mismas operaciones como servidor MCP stdio para agentes (`list_etls`, `describe_etl`,
`run_etl`, `get_run`, `download_artifact`).

---

## 3. Flujo completo de una corrida

Implementado en `orchestrator/service.py::RunService.execute()`. Cada paso escribe en `run.json`
antes de avanzar, así una corrida interrumpida deja rastro de dónde quedó.

```
 1. create_run()               Crea var/runs/<etl_id>/<ts>_<uuid>/ con las 5 subcarpetas
 2. estado → preparing         Se escribe run.json
 3. adapter.validate(request)  Reglas del cliente sobre la petición. Falla → blocked
 4. preflight de estado        ¿Hay recovery pendiente? ¿Ya existe el snapshot del día? → blocked
 5. acquire_lock()             var/state/<etl_id>/<YYYYMM>/.lock. Ya tomado → blocked
 6. stage de inputs            Copia al sandbox, valida extensión, registra tamaño + sha256
 7. stage de estado            Copia el estado corriente del mes al sandbox (si es stateful)
 8. inventario "before"        Foto del directorio output/ antes de ejecutar
 9. adapter.command()          Arma la línea de comando concreta
10. estado → running
11. runner.run()               subprocess con cwd, env filtrado, timeout, drenado en hilos
12. evaluación del proceso     timeout → timed_out; spawn fallido o exit no permitido → failed
13. inventario "after"         Foto del directorio output/ después
14. adapter.outputs()          Postcondiciones: existe, es único, fecha correcta, cambió
15. state_store.promote()      Publica snapshot del día + estado corriente del mes
16. estado → succeeded
17. release_lock()             Siempre, en finally, con verificación de propiedad
```

### Estados terminales

| Estado | Cuándo | Qué hacer |
|---|---|---|
| `succeeded` | Todo pasó | Descargar artefactos |
| `failed` | El proceso falló, o los artefactos no cumplen la postcondición | Revisar `stderr` y `process.command` en `run.json` |
| `timed_out` | Superó `timeout_seconds` | Revisar si el legacy se colgó o si el timeout es corto |
| `blocked` | Nada se ejecutó: validación, lock, snapshot existente, recovery | Es una condición esperada, no un bug. Resolver la causa y reintentar |

### Códigos de error

Se guardan en `run.json` bajo `error.code` y, si el estado es `blocked`, también en `blocker.code`.

| Código | Significado |
|---|---|
| `validation_error` | El adapter rechazó la petición antes de ejecutar |
| `lock_exists` | Hay otra corrida del mismo ETL y mes |
| `snapshot_exists` | Ya se corrió ese ETL ese día |
| `recovery_required` | La promoción de estado quedó a medias en una corrida anterior |
| `spawn_failed` | No se pudo lanzar el proceso |
| `nonzero_exit` | El exit code no está en `allowed_exits` |
| `timeout` | Se agotó el tiempo |
| `postcondition_failed` | Un artefacto declarado falta, está duplicado, tiene fecha equivocada o no cambió |
| `state_unchanged` | El estado promovido es idéntico al anterior y el adapter exigía cambio |
| `promotion_failed` | La promoción falló antes de publicar nada (el estado quedó consistente) |
| `recovery_evidence_failed` | La promoción quedó a medias y ni siquiera se pudo dejar el marcador de recovery. Caso crítico. |
| `orphaned` | La corrida quedó viva cuando el servicio se reinició; la API la marca `failed` al arrancar. |

---

## 4. El catálogo declarativo

Un `manifest.yaml` por cliente en `etls/<cliente>/`. `orchestrator/catalog.py`
(`Catalog.load_workspace`) los descubre todos, los valida estrictamente y falla al
arrancar si algo no cierra. Las carpetas que empiezan con `_` (como `etls/_template/`)
se ignoran.

### Campos

| Campo | Obligatorio | Descripción |
|---|---|---|
| `id` | sí | Identificador único. Convención: `<cliente>.<canal>.<proceso>` |
| `name` | sí | Nombre legible, se muestra en la UI |
| `repository_status` | sí | `present` |
| `readiness` | sí | `ready` / `candidate` / `blocked` |
| `executable` | sí | Si `false`, aparece en el catálogo pero no se puede disparar |
| `project_path` | sí | Carpeta del proyecto legacy, relativa al workspace |
| `working_dir` | no | `cwd` del subprocess |
| `entrypoint` | no | Script que se ejecuta |
| `command` | no | Comando base, por ejemplo `[python, back-base/ejecutar_dia.py]` |
| `fixed_arguments` | no | Flags siempre presentes, por ejemplo `[--chat]` |
| `arguments` | no | Mapa rol → flag CLI |
| `adapter` | no | Ruta de importación `modulo:Clase` (ej. `etl_core.contracts:SubprocessAdapter`); debe satisfacer el Protocol `ETLAdapter` |
| `inputs` | no | Lista de `{role, extensions, required}` |
| `outputs` | no | Lista de `{role, glob, date_format}` |
| `allowed_exits` | no | Exit codes aceptados |
| `timeout_seconds` | no | Debe ser positivo |
| `request_date_format` | no | `YYYYMMDD` / `YYMMDD` / `DDMMYYYY` |
| `output_date_source` | no | `system_date` |
| `environment_allowlist` | no | Variables de entorno que se dejan pasar al subprocess |

### Reglas de validación que conviene conocer

- El root del YAML debe tener exactamente `schema_version: 1` y `etls`. Nada más.
- Ningún campo desconocido: el catálogo rechaza typos en vez de ignorarlos.
- Todas las rutas son relativas y deben quedar dentro del workspace. `..` y rutas absolutas se rechazan.
- Roles de entrada y roles de salida no se pueden repetir dentro de un ETL.
- Las extensiones se declaran con punto: `.csv`, no `csv`.
- El rol de salida debe existir en el enum `ArtifactRole` de `orchestrator/models.py`.
- Un ETL con `executable: true` **exige** `readiness: ready`, un `adapter` registrado, `entrypoint`,
  `command`, `inputs`, `outputs`, `allowed_exits` y `timeout_seconds`. Si falta algo, no arranca.

---

## 5. El contrato de adapter

El contrato es el `Protocol` `ETLAdapter` de `etl_core/contracts.py` (runtime-checkable:
el catálogo valida con `isinstance` al resolver la referencia del manifiesto). Ahí también
viven las excepciones compartidas (`ValidationError`, `PostconditionError`) y el
`SubprocessAdapter` genérico.

```python
class MiAdapter:
    stateful: bool               # ¿el ETL lee/escribe estado persistente mensual?
    requires_state_change: bool  # ¿la corrida debe modificar el estado para ser válida?

    def validate(self, request: RunRequest) -> None:
        """Reglas del cliente sobre la petición. Lanza ValidationError si no procede."""

    def command(self, definition: ETLDefinition, request: RunRequest,
                run: Path) -> tuple[str, ...]:
        """Arma la línea de comando concreta. Todas las rutas apuntan al sandbox."""

    def outputs(self, definition: ETLDefinition,
                before: Mapping[Path, FileEvidence],
                after: Mapping[Path, FileEvidence]) -> tuple[FileEvidence, ...]:
        """Valida postcondiciones y devuelve los artefactos etiquetados por rol.
        Lanza PostconditionError si un artefacto falta, está duplicado,
        tiene la fecha equivocada o no cambió respecto de `before`."""
```

### Reglas para escribir un adapter

1. **Nunca escribas fuera del sandbox.** Todas las rutas de `command()` salen de `run / "..."`.
2. **`validate()` se llama dos veces** (desde el servicio y desde `command()`). Tiene que ser idempotente y sin efectos.
3. **No metas lógica de negocio.** Si estás implementando una regla de cobranza, va en el legacy.
4. **`outputs()` es la línea de defensa.** El exit code `0` no significa que el ETL hizo lo suyo.
5. **Si el ETL legacy no tiene CLI usable**, no lo parchees desde el adapter: escribí un
   `etls/<cliente>/job.py` que exponga una CLI limpia y llamá a eso. Es lo que hacen Bancor,
   EPEC, Frávega, Claro UY, Encuesta CX, Social Learning, Petersen y Naranja X MT.

Un adapter puede además exponer un hook opcional `input_destination(role, source) -> Path`
para controlar dónde se copia cada entrada dentro del sandbox (lo usa Naranja X para
anclar PLANES/PAGOS en `input/diarios/`); sin el hook, el servicio usa
`input/<rol><extensión>`.

### Adapters existentes

| Referencia del manifiesto | Clase | Nota |
|---|---|---|
| `etls.naranjax.ma_chat:MaChatAdapter` | `MaChatAdapter` | Stateful. `--chat` viaja como `fixed_arguments` del manifiesto |
| `etls.naranjax.ma_voice:MaVoiceAdapter` | `MaVoiceAdapter` | Stateful, exige cambio de estado |
| `etls.naranjax.mt_voice:MtVoiceAdapter` | `MtVoiceAdapter` | Vía `mt_voice_job.py` |
| `etls.naranjax.mt_voice_back:MtVoiceBackAdapter` | `MtVoiceBackAdapter` | Tres entradas obligatorias |
| `etls.petersen.adapter:PetersenGestionesAdapter` | `PetersenGestionesAdapter` | Entradas opcionales `approach`, `clientes`, `excluidos` |
| `etl_core.contracts:SubprocessAdapter` | `SubprocessAdapter` | **El genérico**: 10 ETLs de 6 clientes |

> **Advertencia.** `SubprocessAdapter` está mapeado a las bases de Bancor, EPEC, Frávega,
> Claro UY, Encuesta CX y Social Learning (AR/CL) y a los tres PCT de Naranja X. Si lo
> tocás para arreglar algo de un cliente, estás tocando a los otros cinco: cualquier
> cambio ahí requiere correr los 13 e2e (`pytest etls/`).

---

## 6. Puente con el legacy: los `*_job.py`

Cuando el proyecto legacy no tiene una CLI que acepte rutas de entrada y salida, se escribe un
wrapper propio en `etls/<cliente>/job.py`. El wrapper:

1. Recibe `--input` y `--output_dir` apuntando al sandbox.
2. Importa las funciones del legacy.
3. Ancla las rutas del legacy al sandbox.
4. Ejecuta los pasos en cadena, **fail-fast** (el legacy suele tragarse errores por paso).
5. Copia los productos a `output/`.

### El punto frágil

`etls/bancor/job.py` reasigna el `__file__` de un módulo importado para que el legacy
derive su `base_dir` hacia el sandbox:

```python
sys.path.insert(0, str(Path.cwd() / "back-base"))
from procesos import base_generator
base_generator.__file__ = str(work / "procesos" / "base_generator.py")
```

Funciona, pero depende de tres cosas que nadie garantiza: que el `cwd` sea el correcto, que el
legacy siga derivando rutas de `__file__`, y que no calcule su `base_dir` en tiempo de import.
Si alguien toca el legacy de Bancor, esto se rompe sin que ningún test lo anticipe.

**Al escribir un `*_job.py` nuevo, no copies este patrón.** Preferí, en orden:
pasar rutas por argumento → pasar rutas por variable de entorno → como último recurso, monkeypatch,
y documentalo con un comentario explícito.

---

## 7. Cómo el sistema evita corromper datos

Cuatro mecanismos, en orden de aparición:

1. **Sandbox.** El legacy no ve el filesystem real. Si escribe mal, ensucia una carpeta descartable.
2. **Lock por período.** Dos corridas del mismo ETL y mes no pueden solaparse. El lock es un
   directorio (`mkdir` atómico) con el token de propiedad adentro.
3. **Postcondiciones.** Los artefactos se validan contra el glob y la fecha declarados. Un ETL que
   devuelve `0` sin generar nada no pasa.
4. **Promoción durable.** El estado se escribe a temporal, se hace `fsync` del archivo, se publica
   con `os.replace` (atómico) y se hace `fsync` del directorio. Si la segunda publicación falla
   después de la primera, queda `recovery.json` y todo ese ETL/mes se bloquea.

El sistema prefiere **frenar y pedir intervención humana** antes que seguir con estado dudoso. Si
ves corridas en `blocked` con `recovery_required`, no las forces: revisá el linaje en
`var/state/<etl_id>/<YYYYMM>/`.

---

## 8. Convenciones de código

Observadas en el código existente. Respetalas al agregar cosas.

- **Python 3.12+.** Se usan `StrEnum`, `Self`, `X | None`, `is_relative_to`.
- **Inmutabilidad.** Los modelos son `@dataclass(frozen=True)`; los mapas se envuelven en
  `MappingProxyType` en `__post_init__`.
- **Inyección de dependencias por constructor con default.** `Runner(popen=..., clock=...)`,
  `StateStore(replace=..., file_fsync=...)`, `RunService(file_manager=..., log_persister=...)`.
  Es lo que hace testeable el núcleo sin tocar disco. Mantenelo.
- **Excepciones con `code`.** `RunBlockedError` y `StatePromotionError` llevan un atributo `code`
  que termina en `run.json`. Los códigos nuevos se documentan en la sección 3 de este archivo.
- **Errores acotados.** Nada de `except Exception` genérico en el núcleo; se capturan tipos
  concretos. La única excepción documentada es la frontera fail-fast de los `*_job.py`.
- **Sin comentarios decorativos.** Docstring de una línea cuando el nombre no alcanza.
- **Nombres del dominio en inglés en el código, mensajes de usuario en español.** La API responde
  en español porque la consume el equipo de operaciones.
