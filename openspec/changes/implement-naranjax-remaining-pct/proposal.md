# Proposal: Implement Remaining Tipificaciones PCT Jobs

## Intent

Promote `naranjax.ma.chat.pct` and `naranjax.mt.voice.pct` through the
verified unifier platform by reusing the existing stateless PCT adapter under
two new catalog entries — growing the catalog from four to six executable
entries with zero new adapter code and no legacy edits.

## Scope

### In Scope
- Add two catalog entries mirroring `naranjax.ma.voice.pct`: Chat PCT
  (`NARANJAX_PCT_*.csv`) and MT PCT (`DEELO_NAR_USUEVOLTIS_*.txt`), both
  `.csv` input, `YYYYMMDD` system date, exits `[0]`, timeout 900, stateless.
- Register `MaVoicePctAdapter` instances under the new adapter keys in the CLI.
- Add synthetic E2E lifecycle coverage for both entries.
- Deliver one docs slice and one implementation slice, each below 400 lines.

### Out of Scope
- MT `--back` (LOGCALL+historial+M30 → USUEVOLTIS): no legacy contract suite
  exists and it needs multi-input core support — its own SDD change.
- Legacy/product edits, real data, secrets, builds, API/UI, UAT claims.
- Renaming `MaVoicePctAdapter` (noted as future refactor).

## Capabilities

### New Capabilities
None — stateless contract, suffix staging, and the PCT role already exist.

### Modified Capabilities
- `naranjax-ma-chat-daily`: extend the catalog/CLI contract to six executable
  entries.

## Approach

Catalog-only promotion: the PCT adapter is already generic (entry point, globs,
and date formats are catalog data). Two new entries, two new registry keys in
`_adapters()`, focused tests. Nothing else moves.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `registry/naranjax.yaml` | Modified | Two new executable PCT entries |
| `orchestrator/run.py` | Modified | Register two adapter keys |
| `tests/orchestrator/test_catalog.py` | Modified | Six-entry promotion contract |
| `tests/e2e/test_naranjax_remaining_pct.py` | New | Parametrized synthetic lifecycle for both |
| existing catalog-loading tests | Modified | Register new adapter stubs |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Adapter reuse hides a per-job difference | Low | Both entry points verified: Chat is byte-identical; MT shape-verified with its 7-passed suite |
| MT default output dir is cwd-relative | Med | Adapter always passes explicit sandbox `--output_dir` (existing behavior) |
| `.txt` output confuses the pct role | Low | Glob and extension come from the catalog; classifier is glob-driven |

## Rollback Plan

Revert the implementation PR: entries, registrations, and tests travel
together. Evidence remains.

## Dependencies

- PCT stateless chain (#40/#42), MT contract fix (#44). No new dependency.

## Success Criteria

- [ ] Catalog exposes six executable entries; selection resolves each key.
- [ ] Both new jobs run synthetically end-to-end: one today-dated artifact,
      `state: not_applicable`, no lineage.
- [ ] One real fixture-driven platform run per new entry succeeds.
- [ ] All existing suites stay green; status is implementation-ready only.
