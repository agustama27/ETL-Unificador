# Exploration: plan-mvp-etl-unificador-naranjax

## Current State

### Outcome

The recommended pilot remains `SOHO-Chat-NX_MA-ETL/back-base/ejecutar_dia.py`, invoked as a subprocess through a narrow adapter. The conceptual unified CLI can map to it, but it is **not yet safe as a transparent one-to-one wrapper**: output filenames and row dates use the machine date rather than `--fecha`, state is cross-run and non-transactional, retries for the same business date fail on an immutable snapshot, and `--sin_planes_hoy` does not prevent PLANES auto-discovery.

The requested branch already exists and is checked out: `feature/plan-mvp-etl-unificador-naranjax`. The root currently has the two authoritative documents as untracked files. No legacy source was modified.

### Repository inventory

| Project | Exists | Documentation | Primary entry points | Dependencies | Tests | Runtime directories |
|---|---|---|---|---|---|---|
| `SOHO-Chat-NX_MA-ETL/` | Yes | `PLAN_DESARROLLO_CHAT_ETL_NARANJAX_MA.md`, `packaging/BUILD.md` (no README) | `back-base/ejecutar_dia.py`; `naranjax_etl.py --cli`; `back-resultados/etl_tipificaciones_ia_voz_pct.py`; UI by default | `pandas>=2.2,<3.0`, `openpyxl>=3.1,<4.0`, `customtkinter>=5.2,<6.0` | `tests/`, `back-base/tests/`, `back-resultados/tests/` | Daily defaults under `back-base/{archivo-recibido,diarios/entrada,estados,base-generada,logs,diarios/procesados}`; several default folders are absent in the current Chat tree and are created only where code calls `mkdir`. PCT uses `back-resultados/{roman,base-generada}`. |
| `soho-naranjaX-MA-etl/` | Yes | `README_ETL.md`, phase plans/status files, `PLAN_BACK_RESULTADOS_V2.md`, `packaging/BUILD.md` | `back-base/ejecutar_dia.py`; `naranjax_etl.py --cli`; separate PCT entry point; UI by default | Same three runtime packages | Broad `tests/`, `back-base/tests/`, `back-resultados/tests/` | Daily defaults under `back-base/{archivo-recibido,diarios/entrada,estados,base-generada,logs,diarios/procesados}`; PCT under `back-resultados/{roman,base-generada}`. |
| `soho-naranjaX-MT-etl/` | **Yes, verified** | `CLAUDE.md`, `plan_correccion_etl.md`, `plan_back_resultados_naranja_x.md`, `packaging/BUILD.md` | `main.py`; `naranjax_mt_etl.py --cli`; individual `python -m procesos.*`; back-results/PCT entry points | Base pipeline uses stdlib; `requirements-packaging.txt` has `customtkinter>=5.2`, `pyinstaller>=6.0` | Only `back-resultados/tests/` discovered | Base input/output: `back-base/base_recibida/` and `back-base/base_procesada/`; CLI output can be overridden and creates `logs/` and `procesados/`, but current core writes no log/state files. Back-results uses `back-resultados/back_recibida/{logcall,historial}` and `back-resultados/back_procesada/`. |

No root `openspec/config.yaml` or main specs existed when exploration started.

### Chat pilot: exact executable contract

Evidence: `SOHO-Chat-NX_MA-ETL/back-base/ejecutar_dia.py`, `core/modelos.py`, `core/procesar_dia.py`, `back-base/back_base_etl/{constants,io,estado_persistente,transformers,update_estado}.py`.

#### Command and arguments

```text
python back-base/ejecutar_dia.py
  [--fecha YYYYMMDD] [--mes YYYYMM]
  [--input BASE.xlsx]
  [--diarios_dir DIR] [--estado_dir DIR] [--output_dir DIR]
  [--logs_dir DIR] [--procesados_dir DIR]
  [--planes PLANES.xlsx] [--pagos PAGOS.csv]
  [--chat] [--sin_planes_hoy]
```

- Argparse marks no argument as required because every path has a legacy default. Operationally, the base Excel is required when monthly state does not exist or is empty.
- `--fecha` defaults to today in `YYYYMMDD`; only digit length is validated later by state persistence. It determines log name, processed-input folder, and state snapshot.
- `--mes` defaults to `fecha[:6]` and selects the state loaded. A mismatched explicit month can load one month and save another because save derives month from `--fecha`.
- `--input` is the monthly Excel. `load_input()` accepts sheet aliases `Asignacion`, `Asignación`, `ASIGNACION`, or `Asignacion M90 - *` and maps required business columns by aliases.
- PLANES is an `.xlsx` with sheet `default_1`. Explicit `--planes` wins; otherwise `diarios_dir` auto-detects the last lexicographically sorted `.xlsx` whose name contains `planes` or `cartera`.
- PAGOS is CSV with `;` or `,` auto-detection. It is processed **only when explicit `--pagos` is supplied** by this entry point; omission sets `usar_pagos=False`, so residual auto-detected PAGOS is ignored.
- `--chat` adds CHAT output; ROMAN and E1KIA are still always generated.
- `--sin_planes_hoy` only forces CHAT `tiene_planes=False`. It does not disable loading or auto-detection of a PLANES file. Safe no-PLANES execution therefore also requires an isolated empty `diarios_dir` and no `--planes`.
- Daily files are copied, not moved, to `<procesados_dir>/<fecha>/`; duplicate names gain `__N` suffixes.

#### Business behavior and outputs

- Initial state keeps only monthly rows with `cajon=M90` and `ecosistema=PURO`.
- PLANES updates debt/cajón and dynamic plan fields by product, with document fallback; `CAN` products are excluded. A configurable guard `NARANJAX_PLANES_MIN_COVERAGE` defaults to `0.01` and fails on insufficient ROMAN plan coverage.
- PAGOS aggregates by product, subtracts positive `importe_pago` from total/current debt, updates `recupero` and `tipo_pago`, and removes `RECUPERO=SI` rows.
- CHAT consolidates one row per DNI. Debt-source priority is `planes > pagos > api`; API source emits `monto_total_vencido=0`. Plan values come from the first product row with plan data. `tiene_planes` is the conjunction of real plan data and `planes_disponibles_hoy`.
- ROMAN: `NARANJAX_MA_ROMAN_YYYYMMDD.csv`, semicolon UTF-8/LF, one row per product.
- CHAT: `NARANJAX_MA_CHAT_ROMAN_YYMMDD.csv`, semicolon UTF-8/LF, one row per DNI.
- E1KIA: `NARANJAX_MA_E1KIA_YYMMDD_sinestrategia.csv`, semicolon UTF-8/LF, columns `tel_1,tel_2,tel_3`.
- **All three output suffixes use `date.today()`**, not `--fecha`; `fecha_limite_sistema` also uses the machine date in ISO form. Backdated/forward-dated runs therefore produce names/content inconsistent with the requested date and can overwrite same-machine-day outputs.

#### Logs, state, failure, and exit codes

- Direct daily entry point writes console/stderr plus `<logs_dir>/<fecha>.log` in UTF-8.
- State is `<estado_dir>/estado_YYYYMM.csv` plus immutable `<estado_dir>/estado_YYYYMMDD.csv`. A retry with the same `--fecha` fails because the snapshot cannot be overwritten.
- Core catches all exceptions and returns `ResultadoDia(status="error")`; the entry point logs errors and exits `1`. Success falls through with exit `0`; argparse errors exit `2`. Failures before core invocation follow normal Python nonzero behavior.
- State/output changes are not transactional. CHAT is written before PLANES coverage validation; ROMAN/E1KIA are written before `guardar_estado()`. A failure after those writes can therefore leave partial or apparently valid outputs, and a failure while persisting state after the monthly current write can leave current state without its matching snapshot. A same-date snapshot collision does **not** cause that state-write sequence: `guardar_estado()` checks for the existing immutable snapshot before either state file is written.
- The top-level `python naranjax_etl.py --cli` is not a substitute for the pilot: it requires `--base`, effectively requires `--planes` unless `--inicio-mes-sin-diarios`, exposes no `--chat`, and does not create a daily file logger.

### MA Voice comparison

Evidence: `soho-naranjaX-MA-etl/back-base/ejecutar_dia.py`, `core/{modelos,procesar_dia,runtime_paths}.py`, `back-resultados/etl_tipificaciones_ia_voz_pct.py`.

| Concern | MA Chat | MA Voice |
|---|---|---|
| Daily outputs | ROMAN + E1KIA; optional CHAT | ROMAN + E1KIA; no CHAT |
| Chat flags | `--chat`, `--sin_planes_hoy` | Absent |
| Base default | `Formato completo de archivo de entrada.xlsx` | `NARANJAX_MA_BaseMensual.xlsx` |
| PAGOS omission in direct daily CLI | Disabled; no auto-detection | `usar_pagos=True`; may auto-detect residual PAGOS |
| State | Same monthly current + immutable daily snapshots | Same |
| PLANES | Optional/direct auto-discovery; same coverage guard | Same |
| Output dates | Machine date, not `--fecha` | Same |
| Runtime env on top CLI | Config paths | `NARANJAX_ESTADO_DIR`, `NARANJAX_OUTPUT_DIR`, `NARANJAX_RUNTIME_BASE_DIR`, legacy `NARANJAX_DEV_OUTPUT_DIR`, then config |

PCT is a separate job, not an output of daily `procesar_dia()`: `python back-resultados/etl_tipificaciones_ia_voz_pct.py [--input FILE] [--output_dir DIR] [--log_level LEVEL]`. If input is omitted it selects newest `.csv/.xlsx/.xls` from `back-resultados/roman/`. It emits `NARANJAX_PCT_YYYYMMDD.csv`, pipe-delimited, cp1252, seven columns, using machine date. Exit is `0` on success and `1` on handled failure; argparse errors are `2`.

Current verification found a real MA PCT regression: `python -m pytest back-resultados/tests -q` returned **1 failed, 26 passed**. `test_prioriza_columnas_roman23_para_dni_y_observaciones` expected `TIPIFICACION=11` but got `7`. MA daily/CHAT focused checks passed: 13 integration/CHAT tests plus 3 entry-point/PAGOS tests.

### MT verification

`soho-naranjaX-MT-etl/` is present and materially different from MA:

- `python main.py` auto-selects newest `back-base/base_recibida/*.txt`, produces `NARANJAX_MT_ROMAN_YYMMDD.csv`, then `NARANJAX_MT_E1KIA_YYMMDD.csv` in `back-base/base_procesada/`.
- Explicit individual commands are `python -m procesos.base_generator <input.txt>` and `python -m procesos.phone_extractor <roman.csv>`.
- `python naranjax_mt_etl.py --cli [--base TXT] [--estado DIR] [--salida DIR]` is a separate UI/CLI facade. Its `ConfigDia` contains state/log/processed paths, but current `core/procesar_dia.py` only creates those directories; it does not persist state or log files.
- `python main.py --back [--logcall FILE] [--historial FILE] [--m30 FILE] [--back-output-dir DIR] [--strict-phone-quality] [--max-phone-irrecoverable-ratio 0.05]` handles back-results.
- Base flow catches `FileNotFoundError`/`ValueError` and exits `1`; facade maps non-`ok` result to `1`; success is `0`.
- Its PCT/back-results suite currently has a contract mismatch: **1 failed, 6 passed**, expecting `USUOLOS` while implementation emits `USUEVOLTIS` (the latter agrees with `CLAUDE.md`). This appears to be stale test/document evolution, but must be resolved before declaring the adapter ready.

### Initial catalog shape

The catalog should separate adapter readiness from repository presence and model path roles explicitly:

```yaml
schema_version: 1
etls:
  - id: naranjax.ma.chat.daily
    name: Naranja X MA Chat - Proceso diario
    status: adapter_candidate_with_guardrails
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
    required_inputs: [base_mensual]
    optional_inputs: [planes, pagos]
    output_patterns:
      - NARANJAX_MA_ROMAN_*.csv
      - NARANJAX_MA_CHAT_ROMAN_*.csv
      - NARANJAX_MA_E1KIA_*_sinestrategia.csv
    stateful: true
    request_date_format: YYYYMMDD
    output_date_source: system_date
    timeout_seconds: 900
    environment_variables: [NARANJAX_PLANES_MIN_COVERAGE]
```

The other initial records should be `naranjax.ma.voice.daily` (`adapter_candidate_with_guardrails`), `naranjax.ma.voice.pct` (`pending_failing_contract_test`), and `naranjax.mt.voice.daily` (`repository_verified_pending_adapter_design`). Schema should additionally support `output_date_format`, `state_scope`, `retry_policy`, `success_exit_codes`, and `postconditions`; these are necessary for the discovered legacy behavior.

### Unified CLI compatibility

The conceptual command can be translated as follows:

```text
unified --fecha     -> legacy --fecha
unified --base      -> legacy --input
unified --planes    -> legacy --planes (only when present)
unified --pagos     -> legacy --pagos (only when present)
adapter fixed       -> --chat
adapter generated   -> explicit --diarios_dir, --estado_dir, --output_dir,
                       --logs_dir, --procesados_dir
```

This mapping is syntactically valid and verified against `--help`, but safe execution requires adapter guardrails: an empty per-run daily-input directory when PLANES is absent; a durable state directory outside the disposable run sandbox; preflight rejection or explicit retry policy for an existing daily snapshot; before/after output inventory rather than trusting requested-date filenames; and serialized access per state month. Until date semantics are fixed or explicitly accepted, the unified API must report both `business_date` and `artifact_date` rather than claim they are identical.

## Affected Areas

- `registry/naranjax.yaml` — future catalog and adapter contract; do not create until proposal/design approval.
- `orchestrator/models.py` — future definitions for ETL, inputs, outputs, state scope, and run result.
- `orchestrator/runner.py` — future subprocess execution, timeout, exit/stdout/stderr capture, and process isolation.
- `orchestrator/run_store.py` — future `runs/<etl_id>/<timestamp>/run.json` and lifecycle states.
- `orchestrator/file_manager.py` — future staging, output diffing, processed-file capture, and durable-state binding.
- `orchestrator/logging_utils.py` — future combined subprocess stream and legacy file-log capture.
- `adapters/naranjax/ma_chat.py` — future translation and guardrails documented above.
- `SOHO-Chat-NX_MA-ETL/back-base/ejecutar_dia.py` — pilot legacy boundary; inspect/invoke, do not modify in MVP.
- `soho-naranjaX-MA-etl/back-resultados/` — PCT contract currently has one failing test; out of initial pilot.
- `soho-naranjaX-MT-etl/` — verified present but architecturally distinct; out of initial pilot.

## Approaches

1. **Subprocess adapter over `back-base/ejecutar_dia.py`** — stage inputs, pass every mutable path explicitly, bind durable monthly state, capture process evidence, and detect artifacts by filesystem diff.
   - Pros: preserves legacy rules; exposes CHAT flags; minimum blast radius; exit behavior is observable.
   - Cons: requires guards for date mismatch, partial side effects, retries, and shared state concurrency.
   - Effort: Medium

2. **Wrap `naranjax_etl.py --cli`** — use the packaged/public facade.
   - Pros: already validates paths and has a stable executable route.
   - Cons: no `--chat`; PLANES is effectively mandatory; no daily legacy log file; cannot satisfy pilot contract without changing legacy code.
   - Effort: Medium, but unsuitable

3. **Import `core.procesar_dia()` in-process** — construct dataclasses directly and consume `ResultadoDia`.
   - Pros: richer structured result and fewer output-discovery heuristics.
   - Cons: couples interpreter/dependencies/global logging/sys.path to legacy internals; weakens isolation and timeout/exit-code semantics; contradicts the requested legacy-job boundary.
   - Effort: High operational risk

## Recommendation

Proceed to proposal with Approach 1 and scope the first deliverable to `naranjax.ma.chat.daily`. The adapter should use a per-run input/output/log/processed sandbox but a separately managed durable state root keyed by ETL and month. It should serialize runs sharing that state, preflight immutable snapshots, capture stdout/stderr plus the legacy `<fecha>.log`, inventory output directory before/after, and mark runs failed if expected CHAT/ROMAN/E1KIA artifacts are absent even when exit code is zero.

Do not promise arbitrary business-date execution in the MVP. Either constrain `--fecha` to the machine date or make the output-date discrepancy an explicit accepted limitation; changing the legacy output date source would be a separate, tested legacy change. Keep MA Voice, PCT, and MT as later adapter work units. The expected implementation will likely exceed the 400-line review budget, so tasks should be sliced by deliverable (contracts/catalog, run storage/file staging, subprocess runner, Chat adapter/end-to-end docs/tests), each with its own verification and rollback boundary.

## Risks

- Machine-date output naming/content conflicts with requested `--fecha`.
- Non-transactional writes can leave outputs/current state after a failed run.
- Immutable snapshots make same-date retries fail; different concurrent runs can corrupt shared monthly state.
- `--sin_planes_hoy` does not suppress PLANES discovery without input-directory isolation.
- Direct Chat and Voice CLIs differ in PAGOS auto-detection, so one generic argument policy is unsafe.
- Explicit `--mes` can diverge from the month derived from `--fecha`.
- Daily outputs overwrite by system date and fixed prefix.
- PCT tests currently fail in MA; MT back-results tests disagree with current `USUEVOLTIS` contract.
- Existing build/data artifacts and temporary directories are present in legacy trees; the unifier must not copy or commit them indiscriminately.
- `NARANJAX_PLANES_MIN_COVERAGE` changes fail-fast behavior and must be recorded in run metadata.

### Unresolved questions

1. Must MVP support backdated/forward-dated business dates, or may it require `--fecha == local machine date`?
2. Is durable monthly state shared with existing manual legacy operation, or should the unifier own a separate state lineage initialized from the monthly base?
3. What retry policy is acceptable for an existing `estado_YYYYMMDD.csv`: reject, resume, or require a new operator-approved lineage?
4. Is PLANES truly optional on normal Chat days, and should omission always imply `--sin_planes_hoy`?
5. What production timeout and state-locking scope are required?
6. Should current PCT failures block only PCT adapters or the whole Naranja X catalog release?

## Ready for Proposal

Yes, with the initial proposal limited to the guarded subprocess integration of `naranjax.ma.chat.daily` and with the business-date/state-lineage questions made explicit acceptance decisions. MA Voice, PCT, and MT should remain cataloged but out of the first implementation slice.
