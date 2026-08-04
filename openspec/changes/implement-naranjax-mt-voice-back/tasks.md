# Tasks: Implement Naranja X MT Voice Back (USUEVOLTIS)

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 500–600 total; slice 1 220–280, slice 2 260–320 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 multi-input core → PR2 back adapter/promotion/E2E |
| Delivery strategy | auto-chain, resolved |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

## Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|---|---|---|---|
| 1 | `RunRequest.extras`, staging, CLI `--input`, `anomalies` role, daily extras rejection | PR1 | Behavior-neutral for existing entries |
| 2 | Back adapter, seventh catalog entry, E2E, real run, SDD close | PR2 | After PR1 merges |

## Hard Decision Gate

PR2 MUST NOT start until PR1 is merged and its cumulative suite passes. Each
slice MUST stay below 400 changed lines. Legacy/data edits, builds, and
production/UAT claims remain prohibited.

## Phase 1: PR1 — Multi-Input Core

- [ ] 1.1 RED — Extend `tests/orchestrator/test_service.py` with truthful
      extras staging (names, hashes, extension gate) driven by a synthetic
      definition; extend CLI tests for repeatable `--input ROLE=PATH` and
      malformed values; extend daily adapter tests to reject extras; update
      `tests/orchestrator/test_models.py` for `extras` immutability and the
      `anomalies` role. Confirm failures.
- [ ] 1.2 GREEN — Add `RunRequest.extras` and `ArtifactRole.ANOMALIES`;
      extend `_stage_inputs` role resolution; add the CLI argument; add the
      extras guard to the four existing adapters. Rerun focused tests.
- [ ] 1.3 VERIFY — `python -m pytest tests -q`; numstat below 400.

## Phase 2: PR2 — Back Adapter, Promotion, E2E

- [ ] 2.1 RED — Create `tests/adapters/naranjax/test_mt_voice_back.py`
      (exact command, extras completeness, today gate, dual-output
      classification); update catalog tests for seven entries; create
      `tests/e2e/test_naranjax_mt_voice_back.py` (success both artifacts,
      non-today, missing extra, nonzero, missing output, no lineage,
      redaction); extend the synthetic channel map. Confirm failures.
- [ ] 2.2 GREEN — Create `adapters/naranjax/mt_voice_back.py`; add the
      seventh catalog entry; register the adapter key. Rerun focused tests.
- [ ] 2.3 VERIFY — Full suite; MT legacy suite (10 passed, untouched); one
      real fixture-driven platform run; update the plan doc; record
      apply-progress and verify-report; numstat below 400.
