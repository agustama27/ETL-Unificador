# Design: Implement Guarded Naranja X MA Chat MVP

## Technical Approach

Add root packages around unchanged `SOHO-Chat-NX_MA-ETL/back-base/ejecutar_dia.py`. Catalog-selected adapters translate requests; `RunService` stages inputs/state, locks the monthly lineage, captures subprocess evidence, validates outputs, then promotes state. No legacy import or edit.

## Architecture Decisions

| Concern | Choice / rationale | Rejected / tradeoff |
|---|---|---|
| Boundary | `sys.executable` argument-array subprocess isolates globals, mutations, dependencies, and timeout. | In-process legacy coupling. |
| Paths | Resolve symlinks; catalog and every destination MUST be relative and contained by injected workspace/run roots. External user inputs are copied; persist/pass only staged run-relative POSIX paths and hashes. | Host paths leak details and permit escape. |
| State | Unifier lineage `var/state/<etl>/<YYYYMM>`; snapshot-first/current-second same-volume `os.replace`. On second failure, atomically write `recovery.json`; snapshot collision also blocks future runs. | Two-file promotion is not transactional. |
| Lock | Fail-fast `.lock` from preflight through promotion using `os.open(O_CREAT|O_EXCL)`, with schema/run/PID/host/UTC/token. Unlink only an owned token; never auto-break stale locks. | Advisory/auto-clean locks are unsafe. |
| Review | Five stacked-to-main, independently revertible TDD slices: PR1A contracts, PR1B catalog, PR2 state, PR3 process, PR4 Chat. PR4 uses table-driven tests and one synthetic E2E. | Broad E2E exceeds 400 lines. |

## Data Flow

```text
CLI -> Catalog -> Adapter -> RunService -> sandbox/lock -> Runner -> diff
                                      -> postconditions -> promote -> run.json
```

## Interfaces / Contracts

`models.py` defines frozen dataclasses and string enums: `RepositoryStatus(present)`, `Readiness(candidate,blocked,ready)`, `RunStatus(preparing,running,succeeded,failed,timed_out,blocked)`, `StateStatus(not_started,staged,promoted,recovery_required)`, `ArtifactRole(roman,chat,e1kia,legacy_log)`; `InputSpec(role,extensions,required)`, `OutputSpec(role,glob,date_format)`, `ETLDefinition(id,name,status,executable,project_path,working_dir,entrypoint,fixed_args,adapter,inputs,outputs,allowed_exits,timeout_seconds,environment_allowlist)`, `RunRequest(etl_id,business_date,base,planes,pagos,no_planes_today,environment)`, `FileEvidence(role,path,size,mtime_ns,sha256)`, `ProcessResult(exit_code,timed_out,timestamps)`, `StateEffect(scope,status)`, and `RunResult(run_id,status,error_code,artifacts,state)`.

`Catalog.load` uses `yaml.safe_load`; requires mapping root, schema 1, ETL list, unique IDs/roles, known keys/enums, positive timeout, and contained paths. Executable entries require `ready`, registered adapter, entrypoint, complete inputs/outputs, exits, and timeout; inert records may be descriptive.

`RunStore` creates `runs/<etl>/<UTC>_<uuid>/{input/diarios,output,logs,state,processed}`. Each lifecycle transition writes schema-1 `run.json`: sorted UTF-8 JSON, relative paths, business/artifact dates, redacted command/allowlisted environment, evidence, postconditions, and state. Atomic write uses a target-directory temporary, flush+`fsync`, then `os.replace`.

`FileManager` allowlists declared extensions, copies then chunk-hashes inputs, and inventories relative path/size/mtime_ns/SHA-256. Changed means new or unequal metadata/hash. State is copied into run `state/`. Promotion fsyncs same-directory temporaries, replaces immutable snapshot then current, and marks `recovery_required` on partial promotion. Manual recovery reconciles snapshot/current and removes marker or stale lock only after inspecting run/process evidence.

`Runner.run(command,cwd,env,timeout,grace=10)` uses `Popen(shell=False)` plus two threads draining UTF-8 streams (`errors=replace`). Timeout performs terminate/wait/kill/wait, joins streams, and returns timed-out evidence. Startup/I/O failures are finalized too. Sensitive configured values are replaced in command, environment, streams, events, and copied legacy log before persistence; unredacted values are never stored.

`MaChatAdapter` requires a real `YYYYMMDD` equal to injected local `today`; month is only derived. It passes staged base, `--fecha`, `--chat`, and all five sandbox directories; PLANES/PAGOS only when supplied. Missing PLANES requires `no_planes_today`, empty `input/diarios`, and `--sin_planes_hoy`. Success requires allowed exit and exactly one changed role-specific ROMAN/CHAT/E1KIA whose filename dates equal local today.

Dependencies are injected: clock (`today`/UTC), UUID factory, replace operation, runner, catalog, store, file manager, and adapter-key map. CLI only builds `RunRequest`, prints run/status, and returns 0 success, 2 blocked/validation, 1 execution failure. Stable `OrchestratorError(code,message)` subclasses: `CatalogError`, `ValidationError`, `PathContainmentError`, `RunBlockedError` (date/snapshot/lock/recovery), `ProcessExecutionError`, `PostconditionError`, `StatePromotionError`, `PersistenceError`; metadata excludes traces/secrets.

## File Changes and Strict TDD Boundaries

| Slice | Exact product boundary | Exact tests / command |
|---|---|---|
| PR1A contracts/foundation | `pyproject.toml`; `orchestrator/{__init__,models}.py` | `tests/orchestrator/test_models.py`; run that path only |
| PR1B catalog/registry | `orchestrator/catalog.py`; `registry/naranjax.yaml` (four inert IDs) | `tests/orchestrator/test_catalog.py`; then cumulative models+catalog |
| PR2 sandbox/state | `orchestrator/{file_manager,run_store}.py` | `tests/orchestrator/{test_file_manager,test_run_store}.py`; run those paths only |
| PR3 process evidence | `orchestrator/{runner,logging_utils}.py`; `tests/support/fake_jobs.py` | `tests/orchestrator/{test_runner,test_logging_utils}.py`; run those paths only |
| PR4 Chat/CLI | `adapters/{__init__,naranjax/__init__,naranjax/ma_chat}.py`; `orchestrator/{service,run}.py`; Chat-only YAML readiness; concise plan status | `tests/support/synthetic_naranjax.py`; `tests/adapters/naranjax/test_ma_chat.py`; `tests/e2e/test_naranjax_ma_chat.py`; run each path separately |

PR4 target is 300–380 changed lines: adapter/service/CLI ≤190, generators ≤50, tests ≤130, docs ≤10. If measured diff exceeds 400, reduce duplicated cases or split before review; never request an implicit exception.

`pyproject.toml`: Python `>=3.12`; runtime `PyYAML>=6,<7`; extras `test` (`pytest>=8.4,<9`) and `naranjax` (`pandas>=2.2,<3`, `openpyxl>=3.1,<4`). No real fixtures, root-wide tests, builds, secrets, or legacy changes.

## Migration / Rollout

No migration. PR1A–PR3 stay inert; PR4 alone enables Chat. Failed sandboxes remain evidence; rollback disables Chat without touching legacy state.

## Open Questions

None.
