# Proposal: Implement Naranja X MT Voice Daily

## Intent

Promote `naranjax.mt.voice.daily` — the last inert catalog entry — through the
verified unifier platform, completing the four-ETL unification. Provide a
unifier-owned wrapper job, an MT adapter reusing the stateless contract, catalog
promotion, and synthetic evidence, without touching legacy code or claiming
production/UAT acceptance.

## Scope

### In Scope
- Add `adapters/naranjax/mt_voice_job.py`: a subprocess entry owned by the
  unifier that imports `procesos.base_generator`/`procesos.phone_extractor`
  from the MT repo (cwd) and runs the exact `main.py` chain with explicit
  `--input`/`--output_dir`, mapping `FileNotFoundError`/`ValueError` to exit 1.
- Add `MtVoiceAdapter`: stateless, today-only, rejects PLANES/PAGOS/no-PLANES
  intents, stages the 33-column TXT as `input/base.txt`.
- Require exactly one new or changed today-dated (`YYMMDD`) `NARANJAX_MT_ROMAN`
  and `NARANJAX_MT_E1KIA` before success.
- Promote the catalog entry, register the adapter in the CLI, add synthetic E2E.
- Deliver two autonomous stacked-to-main slices, each below 400 changed lines.

### Out of Scope
- Legacy/product edits, historical dates, real data, secrets, builds, API/UI.
- The `--back` job (`DEELO_NAR_USUEVOLTIS`): a separate future catalog entry.
- MA production acceptance (UAT remains pending for all four ETLs).

## Capabilities

### New Capabilities
None — the stateless run contract already exists (PCT chain).

### Modified Capabilities
- `naranjax-ma-chat-daily`: extend the guarded catalog/CLI contract to promote
  MT daily, completing the four-entry catalog with zero inert entries.

## Approach

The wrapper is the missing legacy CLI, owned by the unifier: the legacy repo
exposes core functions with explicit paths but no CLI that uses them, so the
adapter invokes a thin subprocess that does — preserving the process boundary
(the orchestrator never imports legacy code) and disabling all autodetection.
`MtVoiceAdapter` mirrors `MaVoicePctAdapter`: shared today-gate, stateless
declaration, shared role-driven output classification for ROMAN + E1KIA.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `adapters/naranjax/mt_voice_job.py` | New | Subprocess wrapper with explicit paths |
| `adapters/naranjax/mt_voice.py` | New | Stateless MT adapter and guards |
| `registry/naranjax.yaml` | Modified | Complete then promote MT metadata |
| `orchestrator/run.py` | Modified | Register MT adapter |
| `tests/adapters/naranjax/test_mt_voice.py` | New | Command, guards, postconditions |
| `tests/e2e/test_naranjax_mt_voice.py` | New | Synthetic lifecycle evidence |
| `tests/orchestrator/test_catalog.py` | Modified | Full-catalog promotion contract |
| `tests/support/synthetic_naranjax.py` | Modified | `mt` channel outputs |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Wrapper drifts from `main.py` semantics | Low | Wrapper is ~30 lines mirroring the exact call chain; unit-tested against the real modules |
| Legacy repo import residue (sys.path) | Low | Wrapper inserts only the run cwd; subprocess dies with the run |
| Machine/request dates diverge | Med | Shared today-only gate; YYMMDD outputs pinned to today |
| Autodetection of residual repo files | Med | `--input` and `--output_dir` always explicit; sandbox inventory diff |

## Rollback Plan

Revert slice 2 to disable MT promotion/CLI selection, then slice 1 to remove
wrapper/adapter/metadata. Failed sandboxes and evidence remain.

## Dependencies

- Current verified catalog, service, runner, stores, locks, evidence model,
  stateless contract, and suffix-preserving staging (PCT chain, PRs #40/#42).
- Green MT back-resultados suite (7 passed) after PR #44. No new dependency.

## Success Criteria

- [ ] Focused adapter, catalog, and synthetic MT E2E tests pass with generated
      fixtures only; MA regressions stay green.
- [ ] Exact MT command always passes staged `--input` and sandbox
      `--output_dir`; daily intents are blocked; no autodetection is reachable.
- [ ] Success requires exactly one changed today-dated ROMAN and E1KIA; no
      state lineage is created by MT runs.
- [ ] The catalog has zero inert entries; status is implementation-ready only.
