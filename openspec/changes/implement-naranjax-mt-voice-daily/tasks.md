# Tasks: Implement Naranja X MT Voice Daily

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 480–560 total; slice 1 260–320, slice 2 220–260 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 wrapper/adapter/inert contract → PR2 promotion/CLI/E2E |
| Delivery strategy | auto-chain, resolved |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

## Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|---|---|---|---|
| 1 | Wrapper job, MT adapter, complete inert catalog metadata | PR1 | Base `main`; safe because MT stays non-executable |
| 2 | Catalog promotion, CLI registration, synthetic E2E, plan/SDD close | PR2 | Fresh branch from `main` after PR1 merges |

## Hard Decision Gate

PR2 MUST NOT start until PR1 is merged and its cumulative suite passes. Each
slice MUST stay below 400 changed lines (`git diff --numstat main...HEAD`).
Legacy/data edits, builds, and production/UAT claims remain prohibited.

## Phase 1: PR1 — Wrapper, Adapter, Inert Contract

- [ ] 1.1 RED — Create `tests/adapters/naranjax/test_mt_voice.py` for the
      exact wrapper command, today gate, daily-intent rejection, and
      ROMAN/E1KIA missing/unchanged/wrong-date/ambiguous classification;
      create wrapper tests driving `mt_voice_job.py` as a subprocess against
      the real `procesos` modules with synthetic TXT fixtures (valid,
      wrong-column-count, empty); update `tests/orchestrator/test_catalog.py`
      for complete inert MT metadata. Confirm assertion-driven failures.
- [ ] 1.2 GREEN — Create `adapters/naranjax/mt_voice_job.py` and
      `adapters/naranjax/mt_voice.py`; complete the inert MT entry in
      `registry/naranjax.yaml` (`.txt` input, MT globs, `YYMMDD`,
      `system_date`, exits `[0]`, timeout 900). Rerun focused tests.
- [ ] 1.3 VERIFY — Run `python -m pytest tests -q`; inspect
      `git diff --numstat main...HEAD` below 400.

## Phase 2: PR2 — Promotion, CLI, E2E

- [ ] 2.1 RED — Create `tests/e2e/test_naranjax_mt_voice.py` covering CLI
      success (both artifacts, `state: not_applicable`, no lineage),
      non-today block, nonzero/timeout/spawn failures, missing output, and
      redaction; extend `tests/support/synthetic_naranjax.py` with an `mt`
      channel; update catalog/CLI tests for full promotion. Confirm failures.
- [ ] 2.2 GREEN — Promote MT in `registry/naranjax.yaml`; register
      `MtVoiceAdapter` in `orchestrator/run.py`. Rerun focused tests.
- [ ] 2.3 VERIFY — Run `python -m pytest tests -q` and the MT legacy suite
      (expected 7 passed, untouched); perform one real fixture-driven platform
      run with a generated synthetic TXT; update
      `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`; record apply-progress and
      verify-report; inspect `git diff --numstat main...HEAD` below 400.
