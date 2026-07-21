# Apply Progress: Implement Guarded Naranja X MA Chat MVP
## Status

PR1A–PR2A contracts, catalog, and sandbox/files are complete: 9/18 revised tasks.

## Completed Tasks

- [x] 1.1 RED — Extant model mapping triangulation produced 2 failed/2 passed.
- [x] 1.2 GREEN — Defensive copies made all four extant model cases pass.
- [x] 1.3 REFACTOR — Model tests stayed green through decoupling and audit.
- [x] 2.1–2.3 — Catalog cycle plus output-glob containment RED/GREEN/refactor.
- [x] 3.1–3.3 — File-manager cycle plus changed-existing remediation; 6 focused/37 cumulative passed.

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

## Superseded Non-Credit History

The removed combined catalog import RED (`ModuleNotFoundError: orchestrator`) and
18/18 oversized GREEN are historical only, superseded, and earn no PR1A credit.
The later fresh PR1B strict-TDD cycle superseded that work.

The combined PR2 WIP reached 422 additions and 12 focused passes but had no
REFACTOR/cumulative credit. PR2A independently replaced its file-only scope;
`run_store.py` and its tests remain deferred to PR2B.

## Test Summary

- PR1B RED: missing module, then unsafe globs 3 failed/24 passed; final 27 focused/31 cumulative.
- PR2A RED: expected missing-module collection error; remediation RED `1 failed, 5 passed`; final 6 focused/37 cumulative.
- Static: `py_compile` and `git diff --check` passed.

## Files / Budget

- Foundation product: 144 lines; focused tests: 89 lines.
- Revised tasks preserve PR1A/PR1B and mark PR2A complete: 9/18 tasks.
- PR1B exact diff against `4e57072`: 387 additions + 12 deletions = 399 lines.
- `git diff --check` required; no commit created.
- PR2A exact diff against `c506e16`: 274 additions + 39 deletions = 313 lines, including hybrid evidence.

## Remaining
- [ ] PR2B metadata/locks/state; PR3 process; PR4 Chat/CLI.

## PR Boundary / Risks
📍 PR2A → PR2B, stacked-to-main, no exception. Catalog remains inert; metadata,
locks, state, runner, adapter, CLI, and legacy changes stay deferred.
