# Tasks: Implement Guarded Naranja X MA Chat MVP

## Review Workload Forecast

| Unit | Scope | Lines |
|---|---|---:|
| PR1A | contracts/foundation (complete) | 210–260 |
| PR1B | catalog/registry (complete) | 399 actual |
| PR2A | sandbox/files | 200–260 |
| PR2B | metadata/locks/state | 320–375 |
| PR3 | process | 300–360 |
| PR4 | Chat/CLI | 340–395 |
| Overall | stacked | 1,769–2,049 |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

No functional size exception.

Evidence: PR1B: 399 lines. Combined PR2: 422 additions; RED collection errors; GREEN 12 passed; no refactor/cumulative. Non-credit; replacements unchecked.

## PR1A/6 — Contracts/foundation

- [x] 1.1 RED — Mapping: 2 failed/2 passed.
- [x] 1.2 GREEN — Four passed.
- [x] 1.3 REFACTOR — Suite/scope green.

Rollback: PR1A revert.

## PR1B/6 — Catalog/registry

- [x] 2.1 RED — Missing catalog/unsafe globs failed.
- [x] 2.2 GREEN — Catalog/YAML/tests/plan added.
- [x] 2.3 REFACTOR — 27 focused/31 cumulative passed; inert 399-line diff.

Rollback: PR1B revert.

## Slice 2A — Sandbox/file management (PR2A/6)

- [x] 3.1 RED — Excluding combined WIP, add `tests/orchestrator/test_file_manager.py` for sandbox directories, containment, extension-before-mutation, copy/hash/relative evidence, and output before/after diff.
- [x] 3.2 GREEN — Add only `orchestrator/file_manager.py` and ≤10 sandbox lines in `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`; budget ≤105 product/≤135 tests/≤10 docs (≤250).
- [x] 3.3 REFACTOR — Deduplicate containment/hash; verify deterministic diff, tests, `git diff --check`, <400 lines.

Focused: `python -m pytest tests/orchestrator/test_file_manager.py -q`. Cumulative: `python -m pytest tests/orchestrator/test_models.py tests/orchestrator/test_catalog.py tests/orchestrator/test_file_manager.py -q`. Depends: PR1B. Rollback: PR2A revert.

## Slice 2B — Run metadata/locks/state (PR2B/6)

- [ ] 4.1 RED — Excluding combined WIP, add `tests/orchestrator/test_run_store.py` for atomic `run.json`, lock collision/manual-stale/owned-token policy, snapshot/recovery prechecks, ordered/partial promotion, `recovery_required`.
- [ ] 4.2 GREEN — Add only `orchestrator/run_store.py` and ≤10 lock/recovery plan lines; budget ≤175 product/≤175 tests/≤10 docs (≤360).
- [ ] 4.3 REFACTOR — Extract helpers; inject replace/clock/UUID failures; audit evidence/tests, `git diff --check`, <400 lines.

Focused: `python -m pytest tests/orchestrator/test_run_store.py -q`. Cumulative: `python -m pytest tests/orchestrator/test_models.py tests/orchestrator/test_catalog.py tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py -q`. Depends: PR2A. Rollback: PR2B revert.

## Slice 3 — Process evidence (PR3/6)

- [ ] 5.1 RED — Add `tests/support/fake_jobs.py` and `tests/orchestrator/{test_runner,test_logging_utils}.py` for interleaving, redaction, nonzero/spawn failure, legacy logs, terminate/grace/kill, and partial evidence.
- [ ] 5.2 GREEN — Add `orchestrator/{runner,logging_utils}.py`; document timeout/evidence in `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`.
- [ ] 5.3 REFACTOR — Deduplicate stream finalization/redaction, inject short test timeouts, and verify no secret reaches persisted results.

Focused: `python -m pytest tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q`. Cumulative: `python -m pytest tests/orchestrator/test_models.py tests/orchestrator/test_catalog.py tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q`. Depends: PR2B. Rollback: revert PR3; state stays inert.

## Slice 4 — Chat adapter/CLI (PR4/6)

- [ ] 6.1 RED — Add table-driven `tests/adapters/naranjax/test_ma_chat.py` and `tests/support/synthetic_naranjax.py` for today/date args, no-PLANES, exact/ambiguous/missing/unchanged outputs, and service failures.
- [ ] 6.2 GREEN — Add `adapters/{__init__,naranjax/__init__,naranjax/ma_chat}.py`, `orchestrator/{service,run}.py`, enable only Chat in YAML, and add one happy-path `tests/e2e/test_naranjax_ma_chat.py`; finalize plan status.
- [ ] 6.3 REFACTOR — Keep adapter/service/CLI ≤190, generator ≤50, tests ≤145, docs ≤10; consolidate fixtures/cases and audit scope.

Focused: `python -m pytest tests/adapters/naranjax/test_ma_chat.py tests/e2e/test_naranjax_ma_chat.py -q`. Cumulative: `python -m pytest tests/orchestrator tests/adapters/naranjax/test_ma_chat.py tests/e2e/test_naranjax_ma_chat.py -q`. Depends: PR3. Rollback: revert readiness/wiring; no executable entry remains.
