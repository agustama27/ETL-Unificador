# Tasks: Implement Guarded Naranja X MA Chat MVP

## Review Workload Forecast

| Slice | Estimate | Risk |
|---|---:|---|
| PR1A contracts/foundation | 210–260 | Low |
| PR1B catalog/registry | 340–395 | Medium; hard gate |
| PR2 sandbox/state | 330–380 | Medium |
| PR3 process evidence | 300–360 | Medium |
| PR4 Chat adapter/CLI | 340–395 | Medium; hard gate |
| Overall | 1,520–1,790 | High |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

Stacked-to-main: PR1A → PR1B → PR2 → PR3 → PR4; no size exception.

Evidence: extant model triangulation first ran 2 failed/2 passed; the removed 586-line combined import RED is superseded, non-credit history.

## Slice 1A — Contracts/foundation (PR1A/5)

- [x] 1.1 RED — In extant `tests/orchestrator/test_models.py`, immutable-mapping triangulation produced 2 failed/2 passed before defensive-copy GREEN.
- [x] 1.2 GREEN — Pass all four extant model cases with only `pyproject.toml` and `orchestrator/{__init__,models}.py` (product ≤145, tests ≤90).
- [x] 1.3 REFACTOR — Keep the extant model suite green while freezing contracts, decoupling catalog, and auditing scope/diff.

Depends: planning PR. Focused/cumulative: model test. Rollback: revert PR1A.

## Slice 1B — Catalog/registry (PR1B/5)

- [x] 2.1 RED — On PR1A, retain catalog cases in `tests/orchestrator/test_catalog.py`; prove missing loader/registry fails.
- [x] 2.2 GREEN — Add only `orchestrator/catalog.py`, `registry/naranjax.yaml`, catalog tests, and ≤10 `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md` lines (catalog ≤200, YAML ≤60, tests ≤125).
- [x] 2.3 REFACTOR — Centralize containment/validation; run focused catalog then cumulative models+catalog tests; audit inert entries and diff ≤395.

Focused: `python -m pytest tests/orchestrator/test_catalog.py -q`. Cumulative: `python -m pytest tests/orchestrator/test_models.py tests/orchestrator/test_catalog.py -q`. Depends: PR1A. Rollback: revert PR1B.

## Slice 2 — Sandbox/state (PR2/5)

- [ ] 3.1 RED — Create `tests/orchestrator/{test_file_manager,test_run_store}.py` for containment, hashing/diff, atomic evidence, collision/lock, seed, promotion order, and blocked partial promotion.
- [ ] 3.2 GREEN — Add `orchestrator/{file_manager,run_store}.py`; document sandbox, stale-lock, and recovery in `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`.
- [ ] 3.3 REFACTOR — Extract atomic-write/owned-lock helpers, inject replace/clock/UUID failures, then audit relative evidence paths.

Focused: `python -m pytest tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py -q`. Cumulative: `python -m pytest tests/orchestrator/test_models.py tests/orchestrator/test_catalog.py tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py -q`. Depends: PR1B. Rollback: revert PR2; inert catalog remains.

## Slice 3 — Process evidence (PR3/5)

- [ ] 4.1 RED — Add `tests/support/fake_jobs.py` and `tests/orchestrator/{test_runner,test_logging_utils}.py` for interleaving, redaction, nonzero/spawn failure, legacy logs, terminate/grace/kill, and partial evidence.
- [ ] 4.2 GREEN — Add `orchestrator/{runner,logging_utils}.py`; document timeout/evidence in `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`.
- [ ] 4.3 REFACTOR — Deduplicate stream finalization/redaction, inject short test timeouts, and verify no secret reaches persisted results.

Focused: `python -m pytest tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q`. Cumulative: `python -m pytest tests/orchestrator/test_models.py tests/orchestrator/test_catalog.py tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q`. Depends: PR2. Rollback: revert PR3; state stays inert.

## Slice 4 — Chat adapter/CLI (PR4/5)

- [ ] 5.1 RED — Add table-driven `tests/adapters/naranjax/test_ma_chat.py` and `tests/support/synthetic_naranjax.py` for today/date args, no-PLANES, exact/ambiguous/missing/unchanged outputs, and service failures.
- [ ] 5.2 GREEN — Add `adapters/{__init__,naranjax/__init__,naranjax/ma_chat}.py`, `orchestrator/{service,run}.py`, enable only Chat in YAML, and add one happy-path `tests/e2e/test_naranjax_ma_chat.py`; finalize plan status.
- [ ] 5.3 REFACTOR — Keep adapter/service/CLI ≤190, generator ≤50, tests ≤145, docs ≤10; consolidate fixtures/cases and audit scope.

Focused: `python -m pytest tests/adapters/naranjax/test_ma_chat.py tests/e2e/test_naranjax_ma_chat.py -q`. Cumulative: `python -m pytest tests/orchestrator tests/adapters/naranjax/test_ma_chat.py tests/e2e/test_naranjax_ma_chat.py -q`. Depends: PR3. Rollback: revert readiness/wiring; no executable entry remains.
