# Tasks: Implement Naranja X MA Voice PCT

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 300–380 total in one slice |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR: adapter + stateless contract + promotion + E2E |
| Delivery strategy | auto-chain, resolved (single slice fits budget) |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: stacked-to-main
400-line budget risk: Medium

## Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|---|---|---|---|
| 1 | PCT adapter, stateless service contract, catalog promotion, synthetic E2E | PR1 | Base `main` after the docs PR merges |

## Hard Decision Gate

The slice MUST stay below 400 changed lines (`git diff --numstat main...HEAD`);
if it exceeds the budget, split the stateless service contract into its own
preparatory PR. Legacy/data edits, builds, and production/UAT claims remain
prohibited.

## Phase 1: PR1 — Adapter, Stateless Contract, Promotion, E2E

- [ ] 1.1 RED — Create `tests/adapters/naranjax/test_ma_voice_pct.py` for the
      exact command, today gate, and PLANES/PAGOS/no-PLANES rejection; extend
      `tests/orchestrator/test_service.py` with a stateless adapter double
      proving preflight/staging/promotion are skipped, lock is held, and
      `postconditions.state == "not_applicable"`; update
      `tests/orchestrator/test_catalog.py` for executable PCT and inert MT.
      Run `python -m pytest tests/adapters/naranjax/test_ma_voice_pct.py
      tests/orchestrator/test_service.py tests/orchestrator/test_catalog.py -q`;
      confirm assertion-driven failures.
- [ ] 1.2 GREEN — Create `adapters/naranjax/ma_voice_pct.py`; add
      `ArtifactRole.PCT`; add `stateful` flags and the service skip branch;
      derive staged suffix from the validated source; promote PCT in
      `registry/naranjax.yaml`; register the adapter in `orchestrator/run.py`.
      Rerun the focused command.
- [ ] 1.3 RED/GREEN — Create `tests/e2e/test_naranjax_ma_voice_pct.py`
      covering CLI success (PCT artifact evidenced, no state lineage),
      non-today block, nonzero/timeout/spawn failures, missing and ambiguous
      outputs, and redaction; extend `tests/support/synthetic_naranjax.py` with
      a `pct` channel. Run `python -m pytest tests/e2e/test_naranjax_ma_voice_pct.py -q`.
- [ ] 1.4 VERIFY — Run the full suite `python -m pytest tests -q`; run the
      legacy contract suite `python -m pytest back-resultados/tests -q` inside
      `soho-naranjaX-MA-etl` (expected 27 passed, untouched); inspect
      `git diff --numstat main...HEAD` below 400; update
      `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md` to record PCT synthetic
      readiness with MT still pending.
