# Tasks: Implement Remaining Tipificaciones PCT Jobs

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 260–330 in one implementation slice |
| 400-line budget risk | Medium |
| Chained PRs recommended | No (docs slice + one implementation slice) |
| Delivery strategy | auto-chain, resolved |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: stacked-to-main
400-line budget risk: Medium

## Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|---|---|---|---|
| 1 | SDD artifacts for the change | Docs PR | This slice |
| 2 | Two catalog entries, CLI keys, catalog tests, parametrized E2E, SDD close | Feat PR | Base `main` after docs merge |

## Hard Decision Gate

The implementation slice MUST stay below 400 changed lines
(`git diff --numstat main...HEAD`). MT `--back`, legacy/data edits, builds,
and production/UAT claims remain prohibited.

## Phase 1: Feat PR — Promotion, CLI, E2E

- [ ] 1.1 RED — Update `tests/orchestrator/test_catalog.py` for six executable
      entries (Chat PCT and MT PCT metadata, adapter keys); create
      `tests/e2e/test_naranjax_remaining_pct.py` parametrized over both
      entries: CLI selection, success artifact/name, `state: not_applicable`,
      non-today block, nonzero, missing output, no lineage, redaction; extend
      `tests/support/synthetic_naranjax.py` with `chat_pct`/`mt_pct` channels.
      Confirm assertion-driven failures.
- [ ] 1.2 GREEN — Add both entries to `registry/naranjax.yaml`; register
      `naranjax.ma.chat.pct` and `naranjax.mt.voice.pct` as
      `MaVoicePctAdapter` instances in `orchestrator/run.py`; register stubs in
      existing catalog-loading tests. Rerun focused tests.
- [ ] 1.3 VERIFY — Run `python -m pytest tests -q`; run both legacy suites
      (Chat back-resultados expected 25 passed; MT back-resultados expected 7
      passed — both untouched); perform one real fixture-driven platform run
      per new entry; update `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`; record
      apply-progress and verify-report; inspect
      `git diff --numstat main...HEAD` below 400.
