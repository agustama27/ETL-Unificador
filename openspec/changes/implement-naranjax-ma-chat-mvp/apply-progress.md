# Apply Progress: Implement Guarded Naranja X MA Chat MVP
## Status

PR1A–PR4B apply evidence is complete: 24/27 revised tasks; PR4C remains pending.

## Completed Tasks

- [x] 1.1 RED — Extant model mapping triangulation produced 2 failed/2 passed.
- [x] 1.2 GREEN — Defensive copies made all four extant model cases pass.
- [x] 1.3 REFACTOR — Model tests stayed green through decoupling and audit.
- [x] 2.1–2.3 — Catalog cycle plus output-glob containment RED/GREEN/refactor.
- [x] 3.1–3.3 — File-manager cycle plus changed-existing remediation; 6 focused/37 cumulative passed.
- [x] 4.1–4.3 — PR2B-A lock-identity remediation; 8 focused/45 cumulative passed.
- [x] 5.1–5.3 — PR2B-B snapshot-first promotion, Win32/POSIX directory durability, and recovery; 10 focused/55 cumulative passed.
- [x] 6.1–6.3 — PR3 concurrent process capture, redacted deterministic logs, timeout escalation, and partial failure evidence; 8 focused/63 cumulative passed.
- [x] 7.1–7.3 — PR4A adapter command/date/PLANES and output-classification contract; 18 focused/81 cumulative passed.
- [x] 8.1–8.3 — PR4B lifecycle plus host-path remediation; 12 focused/93 cumulative passed.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/orchestrator/test_models.py` | Unit | N/A — new file | Immutable mapping cases: 2 failed/2 passed | `4 passed` after defensive copies | Caller mutation plus assignment rejection | Mapping copies centralized |
| 1.2 | `tests/orchestrator/test_models.py` | Unit | N/A — new file | Same extant slice RED | `4 passed in 0.03s` | Enums, ETL, request, evidence | Post-init hooks kept focused |
| 1.3 | `tests/orchestrator/test_models.py` | Unit | 4/4 approval baseline | No new behavior; inherited cycle | Final focused suite green | Four non-trivial cases retained | Tests remain 89 lines |
| 2.1 | `tests/orchestrator/test_catalog.py` | Unit | 4/4 models | Missing module; unsafe globs 3 failed/24 passed | `27 passed` | POSIX traversal/absolute + Windows drive | Helpers centralized |
| 2.2 | `tests/orchestrator/test_catalog.py` | Unit | N/A — new files | Fresh loader/registry RED; containment RED | `27 passed in 0.36s` | 27 schema/metadata/path cases | Typed conversion retained |
| 2.3 | `tests/orchestrator/test_catalog.py` | Unit | 24/24 pre-fix | Containment cycle written first | Cumulative `31 passed` | Cross-platform pattern semantics | Catalog 200; tests 122 lines |
| 3.1 | `tests/orchestrator/test_file_manager.py` | Unit | `31 passed` models/catalog | Missing module collection error | `6 passed` | Traversal/absolute, two hashes, ordered output diff | Cycle retained for GREEN |
| 3.2 | `tests/orchestrator/test_file_manager.py` | Unit | N/A — new files | Same fresh missing-module RED | `6 passed` | Sandbox, copy, hash, and output cases | Containment/hash helpers centralized |
| 3.3 | `tests/orchestrator/test_file_manager.py` | Unit | `6 passed` focused | Changed-existing assertion: `1 failed, 5 passed` | Minimal evidence comparison: `6 passed` | New, changed, and unchanged paths in ordered diff | No further refactor needed; focused suite green |
| 4.1 | `tests/orchestrator/test_run_store.py` | Unit | `6 focused`; `43 cumulative` | Same-path replacement: `1 failed, 6 passed` | `8 passed` | Foreign identity plus post-claim generic lock | Extant cycle merged |
| 4.2 | `tests/orchestrator/test_run_store.py` | Unit | Same independent cycle | Verifier race reproduced before code | `8 passed` | Claim/revalidate/busy-retry paths | Atomic tombstone claim |
| 4.3 | `tests/orchestrator/test_run_store.py` | Unit | `6 passed` focused | Extant remediation RED | `8 focused`; `45 cumulative` | File/parent fsync; 24-way runtime probe (not pytest): 1 owner/23 blocked | Ruff/mypy/compile/diff green |
| 5.1 | `tests/orchestrator/test_state_store.py` | Unit | `45 passed` cumulative | Missing-module collection error | `7 passed` | Snapshot/recovery preflights; second replace failure | Independent RED retained |
| 5.2 | `tests/orchestrator/test_state_store.py` | Unit | N/A — new files | Fresh missing-module RED | `7 passed` | Primary and fallback recovery evidence | Same-volume sibling temporaries |
| 5.3 | `tests/orchestrator/test_state_store.py` | Unit | `7 passed` focused | Windows API injection: `3 failed, 7 passed` | `10 focused`; `55 cumulative` | POSIX plus Win32 open/flush failures | CreateFileW/FlushFileBuffers/CloseHandle; static/diff green |
| 6.1 | `tests/orchestrator/test_runner.py`, `test_logging_utils.py` | Unit/integration | `55 passed` cumulative | Missing runner/logging modules: 2 collection errors | `8 passed` | Success/nonzero, concurrent streams, timeout terminate/kill, spawn failure, legacy/partial evidence | Shared redactor and stream finalization |
| 6.2 | Same PR3 slice | Unit/integration | N/A — new files | Fresh missing-module RED | `8 passed in 0.68s` | Controlled command/cwd/env plus deterministic persistence | Typed terminal result; 900s/10s defaults |
| 6.3 | Same PR3 slice | Unit/integration | `8 passed` focused | Inherited fresh RED | `8 focused`; `63 cumulative` | Secrets absent from command/env/streams/errors/logs | Ruff/mypy/compile/diff and scope audits green |
| 7.1 | `tests/adapters/naranjax/test_ma_chat.py` | Unit | `63 passed` cumulative | Fresh missing `adapters.naranjax.ma_chat`: collection error | `18 passed` | Exact optional/no-PLANES commands and date/omission rejection | Exact tuple retained |
| 7.2 | Same PR4A slice | Unit | N/A — new product files | Same fresh missing-module RED | `18 passed in 0.75s` | Exact success plus 12 role/classification failures | Pure output classifier extracted |
| 7.3 | Same PR4A slice | Unit | `18 passed` focused | Inherited fresh RED | `18 focused`; `81 cumulative` | ROMAN/CHAT/E1KIA × missing/unchanged/wrong-date/ambiguous | Ruff/mypy/compile/diff green |
| 8.1 | `tests/orchestrator/test_service.py` | Integration | `81 passed` cumulative | Fresh missing `orchestrator.service` collection error | `12 passed` | Date, three blockers, three process failures, two output failures, two state failures | Scenario fakes centralized |
| 8.2 | Same PR4B slice | Integration | N/A — new product file | Same fresh missing-module RED | `12 passed in 2.18s` | Success plus every rejected terminal path | Injected lifecycle boundary retained |
| 8.3 | Same PR4B slice | Integration | `12 passed` focused | Arbitrary POSIX/Windows paths failed `1/12` | `12 focused`; `93 cumulative` | Known roots + absolute paths; relative paths/URLs preserved | Shared pre-persistence sanitizer; static/probe green |

## Superseded Non-Credit History

The removed combined catalog import RED (`ModuleNotFoundError: orchestrator`) and
18/18 oversized GREEN are historical only, superseded, and earn no PR1A credit.
The later fresh PR1B strict-TDD cycle superseded that work.

The combined PR2 WIP and later six-case metadata/state GREEN are non-credit.
PR2B-A and PR2B-B now each have independent RED evidence.

The former combined PR4 adapter/service/CLI/E2E evidence is superseded non-credit.
PR4A/B have fresh missing-module RED cycles; PR4C remains deferred.

## Test Summary

- PR1B RED: missing module, then unsafe globs 3 failed/24 passed; final 27 focused/31 cumulative.
- PR2A RED: expected missing-module collection error; remediation RED `1 failed, 5 passed`; final 6 focused/37 cumulative.
- PR2B-A remediation RED: same-path replacement produced `1 failed, 6 passed`; final 8 focused/45 cumulative.
- PR2B-B RED: missing module; Win32 remediation RED `3 failed, 7 passed`; final 10 focused/55 cumulative.
- PR3 RED: missing runner/logging modules; final 8 focused/63 cumulative with synthetic jobs only.
- PR4A RED: missing adapter module caused collection failure; final 18 focused/81 cumulative, preserving the 63-test safety net.
- PR4B RED: missing service, legacy-secret, then host-path leak `1 failed/11 passed`; final 12 focused/93 cumulative.
- Static: Ruff, mypy, `py_compile`, and `git diff --check` passed.

## Files / Budget

- Foundation product: 144 lines; focused tests: 89 lines.
- Revised tasks preserve all slices and mark PR4A/B complete: 24/27 tasks.
- PR1B exact diff against `4e57072`: 387 additions + 12 deletions = 399 lines.
- `git diff --check` required; no commit created.
- PR2A exact diff against `c506e16`: 274 additions + 39 deletions = 313 lines, including hybrid evidence.
- PR2B-A exact diff against `3c2a9a5`: 349 additions + 49 deletions = 398 lines.
- PR2B-B exact diff against `8e84861`: 385 additions + 10 deletions = 395 lines.
- PR3 pre-report diff against `aa24b90`: 350 additions + 10 deletions = 360 lines; report-inclusive final: 388 + 10 = 398.
- PR4A exact diff against `6332096`: 295 additions + 42 deletions = 337 lines; below forecast and hard stop.
- PR4B exact diff against `39dc103`: 387 additions + 12 deletions = 399 lines, report-inclusive; hard stop passes.

## Remaining
PR4C CLI/catalog/E2E remains pending.

## PR Boundary / Risks
📍 PR4A → PR4B, stacked-to-main, no exception. Catalog remains inert; no CLI, E2E, legacy, or real-data change entered scope.
