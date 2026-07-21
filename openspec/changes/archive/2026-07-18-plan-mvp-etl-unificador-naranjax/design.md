# Design: Plan Naranja X ETL Unifier MVP

## Technical Approach

Build a framework-neutral core around legacy subprocesses. The MVP catalogs verified Naranja X jobs but executes only `naranjax.ma.chat.daily`; mutable paths go to a sandbox, while canonical monthly state commits only after successful postconditions. Legacy rules remain unchanged.

## Architecture Decisions

| Decision | Choice and rationale | Rejected alternative / tradeoff |
|---|---|---|
| Legacy boundary | Invoke `SOHO-Chat-NX_MA-ETL/back-base/ejecutar_dia.py --chat`; preserves isolation and behavior. | In-process import couples globals; top-level CLI cannot generate CHAT. |
| State ownership/atomicity | Default to unifier-owned `var/state/<etl_id>/<YYYYMM>/`. Under one ETL/month lock, seed sandbox `state/`, execute there, then promote current state and new immutable snapshot with temp-file + replace only after validation. Failed sandboxes remain evidence; canonical state is unchanged. | Direct shared legacy state permits partial mutation. Sharing with manual operation is an unresolved product choice. |
| Date/retry | Require `business_date == local system date`, derive month from it, and reject an existing snapshot. Report business and discovered artifact dates separately. | Outputs use `date.today()`; overwrite/resume is unsafe. |
| Discovery/success | Diff output inventories; require new/changed files matching all three patterns. Exit `0` is insufficient. | Filename prediction misses machine dates and partial writes. |
| Concurrency | Hold a fail-fast ETL/month filesystem lock across seed, process, validation, and commit; record owner/run ID. | Per-run locks do not protect monthly lineage. |
| API evolution | Expose `CatalogService` and `RunService.execute(RunRequest) -> RunResult`; CLI is a thin caller. Later FastAPI routes call the same service and move execution to workers without changing adapters. | Embedding FastAPI models or request context in the core creates premature coupling. |

## Data Flow

```text
CLI -> Catalog -> Adapter/preflight -> RunStore + sandbox
                                  -> month lock -> staged state -> subprocess
                                  -> output/log diff -> postconditions
                                  -> atomic state commit -> final run.json
```

## Component Responsibilities and Contracts

| Component | Contract |
|---|---|
| `registry/naranjax.yaml` / catalog | Versioned relative-path definitions: readiness, command/arguments, typed inputs, output patterns/date source, state scope, retry, exit codes, timeout, environment allowlist, postconditions. Loader rejects unknown IDs, absolute/escaping paths, duplicate IDs, and executable records not marked ready. |
| `orchestrator/models.py` | Value models for definitions, file specs, request/result, artifacts, state effects, and lifecycle (`preparing/running/succeeded/failed/timed_out/blocked`). |
| `file_manager.py` | Enforce workspace containment, copy inputs, create sandbox directories; absent PLANES means `--sin_planes_hoy` plus empty daily input. Capture hashes, sizes, and inventories. |
| Naranja X adapter | Validate `YYYYMMDD`, map base/PLANES/PAGOS only when supplied, always pass all mutable directories and `--chat`, never pass `--mes` independently, and assert ROMAN/CHAT/E1KIA artifacts. Record `NARANJAX_PLANES_MIN_COVERAGE`; do not inherit undeclared environment overrides. |
| `runner.py` | Use argument arrays, controlled cwd/environment, concurrent stream capture, 900-second timeout, terminate/kill, and stable failures. Preserve partial files without publishing success. |
| `logging_utils.py` | Timestamp structured orchestrator events; persist raw `stdout.log`, `stderr.log`, and copy legacy `<fecha>.log`; redact configured sensitive fields. |
| `run_store.py` | UTC+UUID IDs, atomic `run.json`, lifecycle transitions, and relative artifact references. |

## File Changes and Review Slices

| Slice (rollback boundary) | Files | Verification |
|---|---|---|
| 1 Contracts/catalog | `registry/naranjax.yaml`, `orchestrator/models.py`, catalog tests | Schema/path/readiness tests |
| 2 Evidence/state sandbox | `run_store.py`, `file_manager.py`, tests | Atomic metadata, containment, diff, lock/state promotion tests |
| 3 Process execution | `runner.py`, `logging_utils.py`, tests | Exit, timeout, stream, process-failure tests |
| 4 Chat pilot/docs | `adapters/naranjax/ma_chat.py`, CLI entry point, E2E fixtures, `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md` | Subprocess contract and success/failure E2E |

Each slice keeps tests/docs with behavior and is independently revertible. Total work is likely above 400 changed lines; chained PRs are recommended.

## Testing Strategy

Unit-test validation, containment, lifecycle, discovery, and adapter arguments. Integration-test process evidence and state promotion with fake jobs. E2E-test Chat with synthetic data; prove missing outputs and snapshot collisions leave canonical state unchanged.

## Migration / Rollout

No legacy migration. Start with a fresh unifier-owned lineage initialized from the supplied monthly base; retain failed runs. MA Voice/PCT/MT remain non-executable catalog entries until separate adapter work and failing contracts are resolved.

## Open Product Decisions

- [ ] Permit dates other than local today (requires a separately tested legacy date fix).
- [ ] Share state lineage with manual legacy runs or retain unifier ownership.
- [ ] Whether PLANES omission is operationally valid; MVP requires an explicit “not received” intent, never silent omission.
- [ ] Production timeout/lock wait policy; MVP defaults to 900 seconds and fail-fast lock contention.
- [ ] Whether MA PCT and MT contract failures block only those adapters (recommended) or the whole catalog release.
