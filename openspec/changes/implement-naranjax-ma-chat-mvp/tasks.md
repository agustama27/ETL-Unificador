# Tasks: Implement Guarded Naranja X MA Chat MVP

## Review Workload Forecast

| Unit | Scope | Lines |
|---|---|---:|
| PR1A–PR2A | complete; 9 tasks | 400 / 399 / 313 actual |
| PR2B-A | run metadata/race-safe locks | 250–330 |
| PR2B-B | state promotion/durable recovery | 260–340 |
| PR3 | process | 300–360 |
| PR4 | Chat/CLI | 340–395 |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

No exception; each unit includes tests/docs and rollback. Combined PR2B (391 lines; 6 focused/43 cumulative) is superseded non-credit; 9/21 earlier tasks remain complete.

## Completed foundations

- [x] 1.1–1.3 PR1A — RED 2 failed/2 passed; GREEN/REFACTOR 4 passed.
- [x] 2.1–2.3 PR1B — Catalog RED; 27 focused/31 cumulative; 399 lines.
- [x] 3.1–3.3 PR2A — File-manager RED/GREEN/REFACTOR; 6 focused/37 cumulative; 313 lines.

Rollback: revert the affected PR.

## PR2B-A — Run metadata + race-safe locks

- [x] 4.1 RED — Cover durable `run.json`, collision/manual stale policy, same-path foreign replacement, and a generic lock acquired after release claims the old lock.
- [x] 4.2 GREEN — Use a unique atomic tombstone claim, bounded Windows busy retry, token revalidation, and owned-only cleanup; ≤140 product, ≤150 tests.
- [x] 4.3 REFACTOR — Centralize durable-replace/identity helpers; mypy, Ruff, `py_compile`, `git diff --check`, focused+cumulative green.

Focused: `python -m pytest tests/orchestrator/test_run_store.py -q`. Cumulative: `python -m pytest tests/orchestrator -q`. Depends: PR2A. Rollback: revert PR2B-A; tombstones remain manual evidence.

## PR2B-B — State promotion + durable recovery

- [x] 5.1 RED — Add `tests/orchestrator/test_state_store.py`: preflight-before-write; snapshot-before-current with directory fsync; partial promotion; failed `recovery.json` replace leaves fsynced fallback `recovery_required` evidence and blocks reruns.
- [x] 5.2 GREEN — Add `orchestrator/state_store.py` with durable same-volume replacements and replace-independent fallback marker; ≤150 product, ≤150 tests, ≤40 docs/evidence (≤340).
- [x] 5.3 REFACTOR — Centralize ordering/error translation; use injected POSIX/Win32 directory flush APIs; mypy, Ruff, `py_compile`, `git diff --check`, focused+cumulative green.

Focused: `python -m pytest tests/orchestrator/test_state_store.py -q`. Cumulative: `python -m pytest tests/orchestrator -q`. Depends: PR2B-A. Rollback: revert PR2B-B.

## PR3 — Process evidence

- [x] 6.1 RED — Add `tests/support/fake_jobs.py` and `tests/orchestrator/{test_runner,test_logging_utils}.py` for interleaving, redaction, nonzero/spawn failure, legacy logs, terminate/grace/kill, and partial evidence.
- [x] 6.2 GREEN — Add `orchestrator/{runner,logging_utils}.py`; document timeout/evidence in `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`.
- [x] 6.3 REFACTOR — Deduplicate stream finalization/redaction, inject short test timeouts, and verify no secret reaches persisted results.

Focused: `python -m pytest tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q`. Cumulative: `python -m pytest tests/orchestrator/test_models.py tests/orchestrator/test_catalog.py tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py tests/orchestrator/test_state_store.py tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q`. Depends: PR2B-B. Rollback: revert PR3; state stays inert.

## PR4 — Chat adapter/CLI

- [ ] 7.1 RED — Add table-driven `tests/adapters/naranjax/test_ma_chat.py` and `tests/support/synthetic_naranjax.py` for today/date args, no-PLANES, exact/ambiguous/missing/unchanged outputs, and service failures.
- [ ] 7.2 GREEN — Add `adapters/{__init__,naranjax/__init__,naranjax/ma_chat}.py`, `orchestrator/{service,run}.py`, enable only Chat in YAML, and add one happy-path `tests/e2e/test_naranjax_ma_chat.py`; finalize plan status.
- [ ] 7.3 REFACTOR — Keep adapter/service/CLI ≤190, generator ≤50, tests ≤145, docs ≤10; consolidate fixtures/cases and audit scope.

Focused: `python -m pytest tests/adapters/naranjax/test_ma_chat.py tests/e2e/test_naranjax_ma_chat.py -q`. Cumulative: `python -m pytest tests/orchestrator tests/adapters/naranjax/test_ma_chat.py tests/e2e/test_naranjax_ma_chat.py -q`. Depends: PR3. Rollback: revert readiness/wiring; no executable entry remains.
