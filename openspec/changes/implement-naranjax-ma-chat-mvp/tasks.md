# Tasks: Implement Guarded Naranja X MA Chat MVP

## Review Workload Forecast

| Slice | Estimate | Risk | Further split before apply |
|---|---:|---|---|
| PR1 contracts/catalog | 260–320 | Low | No |
| PR2 sandbox/state | 330–380 | Medium | No |
| PR3 process evidence | 300–360 | Medium | No |
| PR4 Chat adapter/CLI | 340–395 | Medium | No; gate at 400 |
| Overall | 1,230–1,455 | High | Four PR chain already required |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

All PRs base `main`, merge sequentially, target ≤400 lines/≤60 review minutes, and carry `Current slice: PRn/4`. Planning PR #2 (`docs/plan-mvp-etl-unificador-naranjax`) must merge first.

## Slice 1 — Contracts/catalog (PR1/4)

- [ ] 1.1 RED — Create `tests/orchestrator/test_catalog.py` for schema/IDs, inert readiness, enums, executable completeness, duplicate roles, and traversal rejection.
- [ ] 1.2 GREEN — Add `pyproject.toml`, `orchestrator/{__init__,models,catalog}.py`, and four inert entries in `registry/naranjax.yaml`; update slice status in `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`.
- [ ] 1.3 REFACTOR — Freeze contracts, centralize containment/validation, rerun focused tests, and audit no legacy/data/build changes.

Test narrow/cumulative: `python -m pytest tests/orchestrator/test_catalog.py -q`. Dependency: PR #2 merged. Boundary: conventional commit + PR1 to `main`. Rollback: revert PR1; catalog disappears without legacy impact.

## Slice 2 — Sandbox/state (PR2/4)

- [ ] 2.1 RED — Create `tests/orchestrator/{test_file_manager,test_run_store}.py` for containment, hashing/diff, atomic evidence, collision/lock, seed, promotion order, and blocked partial promotion.
- [ ] 2.2 GREEN — Add `orchestrator/{file_manager,run_store}.py`; document sandbox, stale-lock, and recovery in `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`.
- [ ] 2.3 REFACTOR — Extract atomic-write/owned-lock helpers, inject replace/clock/UUID failures, then audit relative evidence paths.

Test narrow: `python -m pytest tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py -q`. Cumulative: `python -m pytest tests/orchestrator/test_catalog.py tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py -q`. Dependency: PR1 merged. Boundary: commit + PR2 to `main`. Rollback: revert PR2; inert catalog remains.

## Slice 3 — Process evidence (PR3/4)

- [ ] 3.1 RED — Add `tests/support/fake_jobs.py` and `tests/orchestrator/{test_runner,test_logging_utils}.py` for interleaving, redaction, nonzero/spawn failure, legacy logs, terminate/grace/kill, and partial evidence.
- [ ] 3.2 GREEN — Add `orchestrator/{runner,logging_utils}.py`; document timeout/evidence in `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`.
- [ ] 3.3 REFACTOR — Deduplicate stream finalization/redaction, inject short test timeouts, and verify no secret reaches persisted results.

Test narrow: `python -m pytest tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q`. Cumulative: `python -m pytest tests/orchestrator/test_catalog.py tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q`. Dependency: PR2 merged. Boundary: commit + PR3 to `main`. Rollback: revert PR3; state stays inert.

## Slice 4 — Chat adapter/CLI (PR4/4)

- [ ] 4.1 RED — Add table-driven `tests/adapters/naranjax/test_ma_chat.py` and generator `tests/support/synthetic_naranjax.py` for today/date args, no-PLANES, exact/ambiguous/missing/unchanged outputs, and service failures.
- [ ] 4.2 GREEN — Add `adapters/{__init__,naranjax/__init__,naranjax/ma_chat}.py`, `orchestrator/{service,run}.py`, enable only Chat in YAML, and add one happy-path `tests/e2e/test_naranjax_ma_chat.py`; finalize plan status.
- [ ] 4.3 REFACTOR — Keep adapter/service/CLI ≤190, generator ≤50, tests ≤145, docs ≤10; consolidate fixtures/cases and run scope audit.

Test narrow: `python -m pytest tests/adapters/naranjax/test_ma_chat.py tests/e2e/test_naranjax_ma_chat.py -q`. Cumulative: `python -m pytest tests/orchestrator tests/adapters/naranjax/test_ma_chat.py tests/e2e/test_naranjax_ma_chat.py -q`. Dependency: PR3 merged. Boundary: commit + PR4 to `main`. Rollback: revert readiness/wiring. Gate: if diff >400, stop and replan PR4; no exception.
