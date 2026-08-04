# Plan del MVP — ETL Unificador Naranja X
## Resultado y camino de revisión
Este plan define un MVP conservador que registra los ETLs Naranja X y ejecuta
`naranjax.ma.chat.daily` y `naranjax.ma.voice.daily` mediante adapters de
subprocess. No cambia los ETLs legacy ni sus reglas de negocio.

### Estado de implementación

Chat y Voice daily están listos para verificación sintética desde el CLI
unificado. Voice PCT y MT permanecen inertes. Esta evidencia NO implica ejecución
con datos reales, aceptación productiva ni UAT: las tres siguen pendientes.

**Resultado propuesto:** catálogo versionado, runner común desacoplado, sandbox
auditable por corrida, estado mensual protegido y un primer CLI que envuelve el
entry point real de Chat MA con guardas explícitas.

### Revisión sugerida (menos de 60 minutos)
1. Confirmar el inventario y los diagnósticos contra la sección **Evidencia**.
2. Revisar el contrato exacto de Chat, en especial fechas, PLANES, estado y fallos.
3. Aprobar o asignar responsable a cada decisión marcada **Abierta**.
4. Validar el schema, el sandbox y `run.json` como contratos del MVP.
5. Confirmar fases, PRs apilados, aceptación y fuera de alcance.

### Decisión solicitada
- Revisar Chat y Voice MA daily como pilotos ejecutables con evidencia sintética.
- Aprobar los defaults provisionales de fecha, estado, retry, lock y timeout.
- Mantener Voice PCT y MT catalogados pero no ejecutables hasta sus propios PRs.

## Alcance y principios
| Tema | Decisión de este plan |
|---|---|
| Frontera legacy | Invocar un proceso; no importar ni refactorizar el core legacy. |
| Primer piloto | `SOHO-Chat-NX_MA-ETL/back-base/ejecutar_dia.py --chat`. |
| Blast radius | Archivos nuevos fuera de los proyectos legacy; rutas relativas. |
| Reglas Naranja X | Preservar exactamente filtros, prioridades, consolidación y formatos. |
| Evidencia | Un exit code `0` no alcanza: validar archivos y registrar metadata. |
| Evolución | Core sin FastAPI; CLI y futura API consumen los mismos servicios. |
| Datos | No versionar inputs reales, outputs, logs, estado, builds ni secretos. |

## Inventario real del repositorio
Los tres proyectos pedidos existen en la rama
`feature/plan-mvp-etl-unificador-naranjax`.

| Proyecto | Documentación verificada | Entry points / comandos | Dependencias | Tests y estado | Directorios runtime |
|---|---|---|---|---|---|
| `SOHO-Chat-NX_MA-ETL/` | `PLAN_DESARROLLO_CHAT_ETL_NARANJAX_MA.md`, `packaging/BUILD.md`; sin README raíz | `python back-base/ejecutar_dia.py`; `python naranjax_etl.py --cli`; PCT separado; UI por defecto | `pandas>=2.2,<3.0`, `openpyxl>=3.1,<4.0`, `customtkinter>=5.2,<6.0` | `tests/`, `back-base/tests/`, `back-resultados/tests/`; checks focalizados de daily/Chat informados verdes | `back-base/{archivo-recibido,diarios/entrada,estados,base-generada,logs,diarios/procesados}`; PCT en `back-resultados/{roman,base-generada}` |
| `soho-naranjaX-MA-etl/` | `README_ETL.md`, planes/estado de fases, `PLAN_BACK_RESULTADOS_V2.md`, `packaging/BUILD.md` | `python back-base/ejecutar_dia.py`; `python naranjax_etl.py --cli`; PCT separado; UI por defecto | Mismas tres dependencias runtime | Suites en raíz, `back-base/tests/` y `back-resultados/tests/`; PCT: **1 failed, 26 passed** | Mismos defaults de daily; PCT en `back-resultados/{roman,base-generada}` |
| `soho-naranjaX-MT-etl/` | `CLAUDE.md`, `plan_correccion_etl.md`, `plan_back_resultados_naranja_x.md`, `packaging/BUILD.md` | `python main.py`; `python naranjax_mt_etl.py --cli`; `python -m procesos.*`; `python main.py --back` | Pipeline base stdlib; packaging agrega `customtkinter>=5.2`, `pyinstaller>=6.0` | Sólo `back-resultados/tests/` detectado; back-results: **1 failed, 6 passed** | `back-base/{base_recibida,base_procesada}`; back en `back-resultados/{back_recibida,back_procesada}` |
Notas: algunas carpetas de Chat nacen recién por `mkdir`; MT usa otra arquitectura
y sus outputs base verificados usan `YYMMDD` (`%y%m%d`); los tests son evidencia focalizada, no una
promesa de suite legacy completa en verde.

## Diagnóstico Naranja X
### Chat MA — candidato con guardas
Es el mejor piloto porque su entry point diario permite generar CHAT mediante
`--chat`, además de ROMAN y E1KIA. Sin embargo, no es seguro envolverlo de forma
transparente: usa fecha de máquina en outputs, muta estado antes de completar
todas las validaciones y autodetecta PLANES.

Reglas a preservar: estado inicial sólo `cajon=M90`/`ecosistema=PURO`; PLANES
actualiza deuda/cajón/planes y excluye `CAN`; el guard
`NARANJAX_PLANES_MIN_COVERAGE` default `0.01` puede fallar; PAGOS agrega por
producto, descuenta importes positivos y elimina `RECUPERO=SI`; CHAT consolida
por DNI con prioridad `planes > pagos > api`, API con vencido `0` y primer plan.

### MA Voice — parecido, pero no intercambiable
| Diferencia | Chat MA | Voice MA |
|---|---|---|
| Outputs diarios | ROMAN + E1KIA + CHAT con flag | ROMAN + E1KIA; no CHAT |
| Flags Chat | `--chat`, `--sin_planes_hoy` | No existen |
| Base default | `Formato completo de archivo de entrada.xlsx` | `NARANJAX_MA_BaseMensual.xlsx` |
| PAGOS omitido | `usar_pagos=False`; no autodetecta | `usar_pagos=True`; puede autodetectar residual |
| Estado | Current mensual + snapshot diario | Igual |
| Fecha de output | Fecha de máquina | Igual |

PCT es otro job:
`python back-resultados/etl_tipificaciones_ia_voz_pct.py [--input FILE]
[--output_dir DIR] [--log_level LEVEL]`. Produce
`NARANJAX_PCT_YYYYMMDD.csv`, separado por `|`, codificación cp1252 y siete
columnas. Su suite registra **1 failed, 26 passed**: esperaba
`TIPIFICACION=11` y obtuvo `7`. Estado: no listo para adapter.

### MT Voice — repositorio verificado, diseño pendiente
- `python main.py` autodetecta el TXT más nuevo, genera ROMAN y luego E1KIA.
- Los pasos explícitos son `python -m procesos.base_generator <input.txt>` y
  `python -m procesos.phone_extractor <roman.csv>`.
- `naranjax_mt_etl.py --cli` expone rutas, pero el core actual sólo crea
  directorios de estado/log/procesados; no persiste esos artefactos.
- La suite de back-results registra **1 failed, 6 passed**: el test espera
  `USUOLOS`, mientras implementación y `CLAUDE.md` indican `USUEVOLTIS`.
- Estado: repositorio presente, contrato conflictivo y adapter no diseñado.

## Contrato exacto del piloto Chat
### Comando legacy y argumentos
```text
python back-base/ejecutar_dia.py
  [--fecha YYYYMMDD] [--mes YYYYMM]
  [--input BASE.xlsx]
  [--diarios_dir DIR] [--estado_dir DIR] [--output_dir DIR]
  [--logs_dir DIR] [--procesados_dir DIR]
  [--planes PLANES.xlsx] [--pagos PAGOS.csv]
  [--chat] [--sin_planes_hoy]
```

Argparse no marca argumentos requeridos porque todos los paths tienen defaults.
Operativamente, la base mensual Excel es obligatoria cuando no existe estado
mensual o está vacío.

| Argumento | Comportamiento real |
|---|---|
| `--fecha` | Default hoy `YYYYMMDD`; nombra log, carpeta procesada y snapshot. |
| `--mes` | Default `fecha[:6]`; selecciona estado cargado. No debe pasarse desalineado. |
| `--input` | Base Excel; acepta aliases de hoja Asignacion/Asignación/ASIGNACION y `Asignacion M90 - *`. |
| `--planes` | Excel, hoja `default_1`; si falta, se autodetecta el último `.xlsx` con `planes` o `cartera`. |
| `--pagos` | CSV `;` o `,`; en Chat directo sólo se procesa si se pasa explícitamente. |
| `--chat` | Agrega CHAT; ROMAN y E1KIA se generan siempre. |
| `--sin_planes_hoy` | Sólo fuerza `tiene_planes=False`; NO impide autodetección de PLANES. |
| Directorios | El adapter debe pasar todos explícitamente; no usar defaults legacy. |

### Outputs
| Artefacto | Patrón | Contrato |
|---|---|---|
| ROMAN | `NARANJAX_MA_ROMAN_YYYYMMDD.csv` | `;`, UTF-8/LF, una fila por producto |
| CHAT | `NARANJAX_MA_CHAT_ROMAN_YYMMDD.csv` | `;`, UTF-8/LF, una fila por DNI |
| E1KIA | `NARANJAX_MA_E1KIA_YYMMDD_sinestrategia.csv` | `;`, UTF-8/LF, `tel_1,tel_2,tel_3` |

Los tres sufijos y `fecha_limite_sistema` usan `date.today()`, no `--fecha`.
Por eso el MVP debe exigir fecha local de hoy y registrar por separado
`business_date` y `artifact_date` descubierto.

### Logs, estado, fallos y exits
- Log legacy: `<logs_dir>/<fecha>.log` UTF-8, además de consola/stderr.
- Estado: `estado_YYYYMM.csv` actual + `estado_YYYYMMDD.csv` inmutable.
- Success: exit `0`; error manejado del core: exit `1`; argparse: exit `2`.
- Otros fallos Python también son nonzero y deben conservar stderr.
- La escritura no es transaccional: CHAT aparece antes del guard de cobertura;
  ROMAN/E1KIA aparecen antes de guardar estado; el current mensual se escribe
  antes del snapshot. Otros fallos posteriores pueden dejar parciales o current mutado.
- Retry con snapshot existente se rechaza antes de escribir current o snapshot.

## Catálogo propuesto: `registry/naranjax.yaml`
El catálogo separa presencia del repositorio, preparación del contrato y
habilitación de ejecución. Todos los paths son relativos al workspace.

```yaml
schema_version: 1
etls:
  - id: naranjax.ma.chat.daily
    name: Naranja X MA Chat - Proceso diario
    repository_status: present
    status: ready
    executable: true
    project_path: SOHO-Chat-NX_MA-ETL
    working_dir: SOHO-Chat-NX_MA-ETL
    command: [python, back-base/ejecutar_dia.py]
    fixed_arguments: [--chat]
    arguments:
      fecha: --fecha
      base_mensual: --input
      planes: --planes
      pagos: --pagos
      no_planes_today: --sin_planes_hoy
      input_dir: --diarios_dir
      state_dir: --estado_dir
      output_dir: --output_dir
      logs_dir: --logs_dir
      processed_dir: --procesados_dir
    required_inputs:
      - {name: base_mensual, extensions: [.xlsx]}
    optional_inputs:
      - {name: planes, extensions: [.xlsx]}
      - {name: pagos, extensions: [.csv]}
    output_patterns:
      - {role: roman, pattern: NARANJAX_MA_ROMAN_*.csv, date_format: YYYYMMDD}
      - {role: chat, pattern: NARANJAX_MA_CHAT_ROMAN_*.csv, date_format: YYMMDD}
      - {role: e1kia, pattern: NARANJAX_MA_E1KIA_*_sinestrategia.csv, date_format: YYMMDD}
    output_date_source: system_date
    stateful: true
    state_scope: etl_month
    retry_policy: reject_existing_daily_snapshot
    success_exit_codes: [0]
    timeout_seconds: 900
    environment_variables: [NARANJAX_PLANES_MIN_COVERAGE]
    postconditions: [new_roman, new_chat, new_e1kia, valid_exit]

  - id: naranjax.ma.voice.daily
    name: Naranja X MA Voz - Proceso diario
    repository_status: present
    status: ready
    executable: true
    project_path: soho-naranjaX-MA-etl

  - id: naranjax.ma.voice.pct
    name: Naranja X MA Voz - Tipificaciones PCT
    repository_status: present
    status: pending_failing_contract_test
    executable: false
    project_path: soho-naranjaX-MA-etl

  - id: naranjax.mt.voice.daily
    name: Naranja X MT Voz - Proceso diario
    repository_status: present
    status: repository_verified_pending_adapter_design
    executable: false
    project_path: soho-naranjaX-MT-etl
```

El schema final debe exigir para registros ejecutables todos los campos del
primer registro. El loader rechazará IDs duplicados, paths absolutos o con escape
del workspace, estados desconocidos y `executable: true` sin adapter listo.

## Arquitectura y componentes
```text
CLI -> CatalogService -> adapter/preflight -> RunService
                                           -> RunStore + sandbox
                                           -> lock ETL/mes + estado staged
                                           -> subprocess + logs
                                           -> diff + postconditions
                                           -> commit atómico de estado
```

| Componente futuro | Responsabilidad |
|---|---|
| `orchestrator/models.py` | `ETLDefinition`, specs de archivos, `RunRequest`, `RunResult`, artifacts, lifecycle y efectos de estado. |
| `orchestrator/catalog.py` | Cargar/validar schema, paths y readiness; resolver por ID. |
| `orchestrator/file_manager.py` | Containment, staging, hashes, inventarios, sandbox, lock y promoción de estado. |
| `orchestrator/runner.py` | Argument array, cwd/env controlados, streams concurrentes, timeout, terminate/kill y exits. |
| `orchestrator/run_store.py` | Run ID UTC+UUID, transiciones y escritura atómica de `run.json`. |
| `orchestrator/logging_utils.py` | Eventos estructurados, `stdout.log`, `stderr.log`, copia de log legacy y redacción. |
| `adapters/naranjax/ma_chat.py` | Preflight y traducción exacta; sin reglas de negocio. |

El core expone `RunService.execute(RunRequest) -> RunResult`. El CLI es un
caller fino; una futura API deberá reutilizar el servicio, no introducir lógica
FastAPI en adapters o modelos del dominio.

## Sandbox y evidencia de corrida
```text
runs/<etl_id>/<run_id>/
├── input/          # copias de inputs y diarios aislados
├── output/         # outputs legacy de esta corrida
├── logs/           # stdout.log, stderr.log, run.log y log legacy
├── state/          # copia staged; nunca fuente canónica directa
├── processed/      # copias legacy de diarios usados
└── run.json

var/state/<etl_id>/<YYYYMM>/
├── estado_YYYYMM.csv
├── estado_YYYYMMDD.csv
└── .lock
```

Flujo: validar y hashear inputs; crear sandbox; adquirir lock; copiar estado
canónico a `state/`; inventariar outputs; ejecutar con paths del sandbox;
inventariar otra vez; validar exits y tres outputs; sólo entonces promover
estado mediante archivo temporal + replace. Un fallo conserva sandbox y no
publica success ni modifica el estado canónico.

### Contrato mínimo de `run.json`
```json
{
  "schema_version": 1,
  "run_id": "20260619T113000Z_<uuid>", "etl_id": "naranjax.ma.chat.daily",
  "status": "succeeded", "business_date": "20260619", "artifact_date": "20260619",
  "started_at": "2026-06-19T11:30:00Z", "finished_at": "2026-06-19T11:32:10Z",
  "command": ["python", "back-base/ejecutar_dia.py", "--chat"], "cwd": "SOHO-Chat-NX_MA-ETL",
  "inputs": [{"role": "base_mensual", "path": "input/base.xlsx", "sha256": "...", "size": 123}],
  "environment": {"NARANJAX_PLANES_MIN_COVERAGE": "0.01"},
  "exit_code": 0, "timed_out": false, "error": null,
  "logs": ["logs/stdout.log", "logs/stderr.log", "logs/20260619.log"],
  "artifacts_before": [], "artifacts_after": [{"role": "chat", "path": "output/NARANJAX_MA_CHAT_ROMAN_260619.csv"}],
  "postconditions": {"roman": true, "chat": true, "e1kia": true},
  "state": {"lineage": "unifier", "scope": "202606", "committed": true}
}
```

Estados: `preparing`, `running`, `succeeded`, `failed`, `timed_out`, `blocked`.
Todos los paths persistidos son relativos. Cada transición de `run.json` es
atómica; debe registrarse incluso si falla el preflight.

## Políticas operativas y decisiones abiertas
| Tema | Default seguro del MVP | Estado / decisión pendiente |
|---|---|---|
| Fecha | `business_date == fecha local del host`; mes derivado, nunca independiente | **Abierta:** soportar históricos requiere cambio legacy probado. |
| Estado | Lineage propia en `var/state/<etl>/<mes>` | **Abierta:** confirmar si debe compartirse con operación manual. |
| Retry | Rechazar si ya existe `estado_YYYYMMDD.csv` | **Abierta:** resume/overwrite sólo con diseño y aprobación operativa. |
| Concurrencia | Lock filesystem fail-fast por ETL/mes desde seed hasta commit | **Abierta:** espera máxima y recuperación de lock huérfano. |
| PLANES omitido | Requiere intención explícita, no pasa `--planes`, usa `--sin_planes_hoy` y `diarios_dir` vacío | **Abierta:** confirmar que omisión es válida en operación normal. |
| PAGOS omitido | No pasar `--pagos`; Chat lo deshabilita | Cerrada para Chat; Voice necesita política distinta. |
| Timeout | 900 s configurable; terminate, espera 10 s y kill; conserva streams, logs y parciales | Cerrada para piloto. |
| Success | Exit permitido + outputs nuevos/cambiados ROMAN, CHAT y E1KIA | Cerrada para piloto. |
| Fallo | Preservar parciales; no promover estado; error estable en metadata | Cerrada para piloto. |
| PCT/MT | Bloqueo sólo del adapter afectado | **Abierta:** aprobación de release por catálogo parcial. |

## Primer CLI unificado y mapping
```bash
python -m orchestrator.run \
  --etl naranjax.ma.chat.daily \
  --fecha 20260619 \
  --base ./inputs/base.xlsx \
  --planes ./inputs/planes.xlsx \
  --pagos ./inputs/pagos.csv
```

| CLI unificado | Legacy / generado por adapter |
|---|---|
| `--fecha` | `--fecha`; valida `YYYYMMDD`, deriva mes y exige hoy local. |
| `--base` | `--input <staged path>`. |
| `--planes` | `--planes <staged path>` sólo si existe. |
| `--pagos` | `--pagos <staged path>` sólo si existe. |
| `--etl` | Selecciona catálogo/adapter; no llega al proceso legacy. |
| Fijo | `--chat`. |
| Generado | `--diarios_dir`, `--estado_dir`, `--output_dir`, `--logs_dir`, `--procesados_dir`. |

El adapter no pasa `--mes`: lo deriva junto con `--fecha` para impedir
desalineación. Sin PLANES, el CLI deberá exigir un flag explícito futuro como
`--sin-planes-hoy`; no debe inferirlo silenciosamente por ausencia de archivo.

## Plan de implementación y cadena de PRs
Estrategia aprobada: **stacked-to-main**. Cada PR apunta a la rama del PR previo
mientras la cadena esté abierta; una vez mergeado el anterior, se retargetea a
`main`. No se mezcla con feature-branch-chain.

```text
main
└─ PR 0 Planificación (actual) 📍
   └─ PR 1 Contratos/catálogo
      └─ PR 2 Sandbox/estado
         └─ PR 3 Proceso/evidencia
            └─ PR 4 Chat/CLI piloto
```

| PR / fase | Inicio y resultado terminado | Verificación | Rollback |
|---|---|---|---|
| 0 Planificación | Dos briefs + SDD aprobados → este plan completo y revisado | Markdown, diff planning-only | Eliminar plan y artifacts SDD |
| 1 Contratos | Plan aprobado → modelos, schema y catálogo no ejecutable | Tests de schema, IDs, readiness y paths | Revertir registry/modelos/tests |
| 2 Sandbox/estado | Contratos estables → run store, staging, diff, lock y promoción | Tests de containment, atomicidad, colisión y estado sin cambios al fallar | Revertir store/file manager/tests |
| 3 Proceso | Sandbox listo → subprocess, streams, logs, timeout y exits | Jobs fake: éxito, error, timeout, stderr y parciales | Revertir runner/logging/tests |
| 4 Chat piloto | Core estable → adapter, CLI y Chat sintético E2E | Argumentos, PLANES omitido, tres outputs, missing output y snapshot collision | Revertir adapter/CLI/E2E |

Cada slice incluye sus tests y docs, apunta a no superar 400 líneas cambiadas o
solicita una excepción explícita, y debe poder revisarse en menos de 60 minutos.

## Criterios de aceptación del MVP funcional futuro
- [x] Catálogo con cuatro IDs; Chat y Voice daily ejecutables, PCT y MT inertes.
- [x] Paths mutables en sandbox; inputs con hash/tamaño y sin datos reales versionados.
- [x] Cada corrida registra `run.json`, streams, log legacy, comando/cwd, exit/timeout/error.
- [x] Diff detecta ROMAN/CHAT/E1KIA; exit `0` con faltantes termina `failed`.
- [x] Registra `business_date`/`artifact_date`; estado se promueve sólo tras postconditions.
- [x] Snapshot existente y concurrencia ETL/mes se bloquean antes de mutar estado.
- [x] PLANES omitido no se autodetecta; fallos/timeouts preservan evidencia.
- [x] Reglas/formatos legacy siguen compatibles; no hay API/UI ni artefactos prohibidos.

## Riesgos y mitigaciones
| Riesgo | Impacto | Mitigación prevista |
|---|---|---|
| Fecha de máquina difiere de negocio | Outputs/filas mal fechados o sobrescritos | Exigir hoy local; registrar ambas fechas. |
| Otros fallos tras escrituras legacy | Parciales o current mutado con exit `1` | Sandbox, diff, postconditions y promoción tardía. |
| Snapshot inmutable existente | Retry rechazado antes de ambas escrituras de estado | Preflight antes de ejecutar. |
| Estado mensual concurrente | Corrupción o pérdida de updates | Lock ETL/mes sobre todo el ciclo. |
| PLANES residual autodetectado | Reglas aplicadas contra intención | `diarios_dir` aislado vacío y flag explícito. |
| Drift Chat/Voice en PAGOS | Adapter genérico incorrecto | Policies por adapter, sin herencia implícita. |
| Streams llenan buffers | Deadlock de subprocess | Captura concurrente de stdout/stderr. |
| Timeout deja hijos | Corrida zombie | terminate, grace, kill y estado `timed_out`. |
| Tests PCT/MT fallando | Readiness engañosa | Estados no ejecutables y PRs separados. |
| Artefactos reales ya presentes | Copia/commit accidental | Allowlist de staging y revisión de diff. |

## Supuestos y preguntas abiertas
Supuestos: Python y dependencias disponibles por subproyecto; lineage inicializada
con base mensual; lock exclusivo y replace atómico en el mismo volumen; E2E sólo
con fixtures sintéticos.

Preguntas: ¿fecha limitada a hoy?, ¿lineage exclusiva o manual compartida?,
¿quién autoriza retry?, ¿omisión de PLANES válida y declarada por quién?, ¿espera
y recuperación de lock?, ¿900 s y grace period?, ¿fallos bloquean sólo PCT/MT?

## Fuera de alcance de esta entrega
- Implementar runner, catálogo, modelos, sandbox, adapters, CLI o stubs.
- Ejecutar ETLs con datos reales o generar outputs/estado runtime.
- API FastAPI, UI, cola, workers, base de datos o cloud storage.
- Modificar, mover o borrar código legacy y sus directorios.
- Cambiar reglas Naranja X, formatos de output o fuentes de fecha.
- Implementar adapters de MA Voice, PCT o MT.
- Soportar fechas históricas, retries destructivos o lineage manual compartida.
- Resolver en este PR los tests fallidos de MA PCT o MT back-results.

## Evidencia y trazabilidad
| Afirmación | Evidencia |
|---|---|
| Objetivo, piloto, entregable y restricciones | `01_objetivo_proyecto_etl_unificador.md`; `02_primer_paso_planificacion_agente_codigo.md` |
| CLI Chat, flags, paths, exits y orden | `SOHO-Chat-NX_MA-ETL/{back-base/ejecutar_dia.py,core/procesar_dia.py}` |
| Outputs, fecha, estado y reglas CHAT | `SOHO-Chat-NX_MA-ETL/back-base/back_base_etl/{constants,io,estado_persistente,transformers,update_estado}.py` |
| Voice/PCT | `soho-naranjaX-MA-etl/{back-base/ejecutar_dia.py,back-resultados/}`; pytest relevado `1 failed, 26 passed` |
| MT | `soho-naranjaX-MT-etl/{main.py,CLAUDE.md,procesos/}`; pytest relevado `1 failed, 6 passed` |
| Decisiones y escenarios | `openspec/changes/plan-mvp-etl-unificador-naranjax/` |

## Aceptación de esta fase de planificación
- [x] Inventario real y diagnósticos trazables incluidos.
- [x] Contrato Chat exacto, diferencias Voice y estado MT documentados.
- [x] Schema, runner, sandbox, `run.json`, políticas y CLI propuestos.
- [x] Fases y cadena stacked-to-main con límites y rollback definidos.
- [x] Riesgos, supuestos, preguntas y fuera de alcance explícitos.
- [x] Ningún código funcional o legacy forma parte de esta entrega.

**Siguiente paso recomendado:** revisión mantenedora de este PR de planificación y
resolución de las decisiones abiertas antes de iniciar PR 1 (contratos/catálogo).
