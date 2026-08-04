# Tasks: Implement Naranja X MA Voice Daily

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 450–520 total; PR1 220–290, PR2 210–260 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 adapter/inert contract → PR2 dispatch/promotion/E2E |
| Delivery strategy | ask-on-risk, resolved |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

## Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|---|---|---|---|
| 1 | Voice adapter plus complete inert catalog contract | PR1 | Base `main`; independently safe because Voice stays non-executable |
| 2 | Catalog dispatch, Voice promotion, synthetic CLI lifecycle, plan status | PR2 | Fresh branch from `main` after PR1 merges |

## Hard Decision Gate

PR2 MUST NOT start until PR1 is merged to `main`, its cumulative suite passes, and `git diff --numstat main...HEAD` proves PR1 below 400 changed lines. No `size:exception`; PCT, legacy/data, builds, and production/UAT claims remain prohibited.

## Phase 1: PR1 — Adapter and Inert Contract

- [x] 1.1 RED — Create `tests/adapters/naranjax/test_ma_voice.py` for exact argument order/month, PLANES/PAGOS combinations, daily-directory equality, today/intent conflicts, and ROMAN/E1KIA missing/ambiguous/unchanged/wrong-date; update `tests/orchestrator/test_catalog.py` to require complete candidate/non-executable Voice metadata and inert PCT/MT. Run `python -m pytest tests/adapters/naranjax/test_ma_voice.py tests/orchestrator/test_catalog.py -q`; confirm failures are assertion-driven.
- [x] 1.2 GREEN — Create `adapters/naranjax/ma_voice.py`, composing `MaChatAdapter.validate/outputs` while owning staged-file isolation and the Voice command without `--chat`/`--sin_planes_hoy`; complete only the inert Voice daily entry in `registry/naranjax.yaml`. Rerun the focused command.
- [x] 1.3 REFACTOR — Keep shared exceptions/classification in `ma_chat.py` unchanged and simplify only new Voice/test helpers. Run `python -m pytest tests/adapters/naranjax/test_ma_voice.py tests/orchestrator/test_catalog.py tests/adapters/naranjax/test_ma_chat.py -q`; inspect `git diff --numstat main...HEAD` and revert PR1 to roll back adapter/metadata together.

## Phase 2: PR2 — Dispatch, Promotion, and E2E

- [x] 2.1 RED — Update `tests/orchestrator/test_catalog.py` for Chat/Voice adapter resolution and Voice-only promotion; create `tests/e2e/test_naranjax_ma_voice.py` for CLI mapping/exits, success artifacts/state/evidence, historical pre-run block, nonzero/timeout/spawn failure, invalid outputs, redaction, and no promotion. Run `python -m pytest tests/orchestrator/test_catalog.py tests/e2e/test_naranjax_ma_voice.py -q`; confirm expected failures.
- [x] 2.2 GREEN — Modify `orchestrator/run.py` to select by `definition.adapter` from injected/default adapters and inject the selected adapter into the service; modify `registry/naranjax.yaml` to promote only Voice daily, and extend `tests/support/synthetic_naranjax.py` with role-specific Voice outputs. Rerun the focused command.
- [x] 2.3 REFACTOR — Deduplicate synthetic helpers and adapter typing without changing Chat; update `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md` to record synthetic implementation readiness only, with PCT/MT inert and UAT pending.
- [x] 2.4 VERIFY — Run `python -m pytest tests/adapters/naranjax/test_ma_voice.py tests/adapters/naranjax/test_ma_chat.py tests/orchestrator/test_catalog.py tests/orchestrator/test_service.py tests/e2e/test_naranjax_ma_voice.py tests/e2e/test_naranjax_ma_chat.py -q`; inspect `git diff --numstat main...HEAD` below 400. Revert PR2 first to disable dispatch/promotion while preserving evidence/state; revert PR1 only afterward.
