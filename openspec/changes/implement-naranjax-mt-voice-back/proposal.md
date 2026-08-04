# Proposal: Implement Naranja X MT Voice Back (USUEVOLTIS)

## Intent

Promote `naranjax.mt.voice.back` — the last legacy job outside the catalog —
completing the seven-entry unification. Requires the platform's first
multi-input contract: generic extra inputs on `RunRequest`, a repeatable CLI
argument, the `anomalies` artifact role, and a stateless back adapter.

## Scope

### In Scope
- Core: `RunRequest.extras` (role → path mapping), staging of extra inputs as
  `input/<role><suffix>` validated by catalog extension specs, repeatable CLI
  `--input ROLE=PATH`, and `ArtifactRole.ANOMALIES`.
- `MtVoiceBackAdapter`: stateless, today-only, rejects PLANES/PAGOS/no-PLANES,
  requires exactly `logcall` and `historial` extras, and invokes
  `main.py --back` with all three staged inputs and the sandbox output dir.
- Catalog entry: base `.txt` (M30) + required extras `logcall`/`historial`
  (`.csv`), outputs USUEVOLTIS + anomalies (`YYYYMMDD`, system date), exits
  `[0]`, timeout 900.
- Synthetic E2E plus one real fixture-driven platform run.
- Two implementation slices below 400 lines each (core, then adapter/CLI).

### Out of Scope
- `--strict-phone-quality` knobs (not exposed; legacy defaults apply).
- Legacy/product edits, real data, secrets, builds, API/UI, UAT claims.

## Capabilities

### New Capabilities
- `multi-input-run-contract`: catalog jobs may declare required extra inputs
  beyond base/planes/pagos, staged truthfully by role.

### Modified Capabilities
- `naranjax-ma-chat-daily`: extend the catalog/CLI contract to seven
  executable entries and the `anomalies` role.

## Approach

Extend, don't fork: `extras` rides the existing `RunRequest`/staging/evidence
machinery; unknown-role staging derives `input/<role><suffix>` exactly like
the suffix-preserving base staging. The adapter mirrors the stateless shape
(PCT/MT daily) plus an extras completeness gate.

## Affected Areas

| Area | Impact |
|---|---|
| `orchestrator/models.py` | `RunRequest.extras`, `ArtifactRole.ANOMALIES` |
| `orchestrator/service.py` | Stage extras by role |
| `orchestrator/run.py` | Repeatable `--input ROLE=PATH`; register adapter |
| `adapters/naranjax/mt_voice_back.py` | New stateless back adapter |
| `registry/naranjax.yaml` | Seventh entry |
| tests | Core staging/CLI, adapter suite, catalog, parametrized E2E |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Extras weaken daily input guarantees | Low | Daily adapters reject extras; catalog specs gate roles/extensions |
| Hour-stamped USUEVOLTIS name breaks date check | Low | `%Y%m%d_` matches the boundary-guarded `YYYYMMDD` regex; pinned in tests |
| Anomalies always written masks failures | Low | Postconditions require BOTH artifacts new and today-dated; exit gate first |

## Rollback Plan

Revert slice 2 (adapter/promotion), then slice 1 (core extras). Evidence
remains.

## Dependencies

- Contract suite #56 (10 passed). Stateless contract and suffix staging
  (PCT/MT chains). No new dependency.

## Success Criteria

- [ ] Catalog exposes seven executable entries; extras stage truthfully.
- [ ] Back runs synthetically end-to-end and via one real fixture-driven run:
      both artifacts, `state: not_applicable`, no lineage, no autodiscovery.
- [ ] Daily adapters reject extras; all prior suites stay green.
