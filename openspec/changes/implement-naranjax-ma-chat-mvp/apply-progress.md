# Apply Progress: Implement Guarded Naranja X MA Chat MVP
## Status

PR1A–PR1B contracts/catalog are complete: 6/15 tasks after PR1B containment remediation.

## Completed Tasks

- [x] 1.1 RED — Extant model mapping triangulation produced 2 failed/2 passed.
- [x] 1.2 GREEN — Defensive copies made all four extant model cases pass.
- [x] 1.3 REFACTOR — Model tests stayed green through decoupling and audit.
- [x] 2.1–2.3 — Catalog cycle plus output-glob containment RED/GREEN/refactor.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/orchestrator/test_models.py` | Unit | N/A — new file | Immutable mapping cases: 2 failed/2 passed | `4 passed` after defensive copies | Caller mutation plus assignment rejection | Mapping copies centralized |
| 1.2 | `tests/orchestrator/test_models.py` | Unit | N/A — new file | Same extant slice RED | `4 passed in 0.03s` | Enums, ETL, request, evidence | Post-init hooks kept focused |
| 1.3 | `tests/orchestrator/test_models.py` | Unit | 4/4 approval baseline | No new behavior; inherited cycle | Final focused suite green | Four non-trivial cases retained | Tests remain 89 lines |
| 2.1 | `tests/orchestrator/test_catalog.py` | Unit | 4/4 models | Missing module; unsafe globs 3 failed/24 passed | `27 passed` | POSIX traversal/absolute + Windows drive | Helpers centralized |
| 2.2 | `tests/orchestrator/test_catalog.py` | Unit | N/A — new files | Fresh loader/registry RED; containment RED | `27 passed in 0.36s` | 27 schema/metadata/path cases | Typed conversion retained |
| 2.3 | `tests/orchestrator/test_catalog.py` | Unit | 24/24 pre-fix | Containment cycle written first | Cumulative `31 passed` | Cross-platform pattern semantics | Catalog 200; tests 122 lines |

## Superseded Non-Credit History

The removed combined catalog import RED (`ModuleNotFoundError: orchestrator`) and
18/18 oversized GREEN are historical only, superseded, and earn no PR1A credit.
Catalog code/tests/YAML must receive a fresh PR1B strict-TDD cycle.

## Test Summary

- PR1B RED: missing module, then unsafe globs 3 failed/24 passed; final 27 focused/31 cumulative.

## Files / Budget

- Foundation product: 144 lines; focused tests: 89 lines.
- Revised tasks preserve PR1A and mark PR1B complete: 6/15 tasks.
- PR1B exact diff against `4e57072`: 387 additions + 12 deletions = 399 lines.
- `git diff --check` required; no commit created.

## Remaining
- [ ] PR2 sandbox/state; PR3 process; PR4 Chat/CLI.

## PR Boundary / Risks
📍 PR1B → PR2, stacked-to-main, no exception. Catalog is inert; runner/adapter/CLI stay deferred.
