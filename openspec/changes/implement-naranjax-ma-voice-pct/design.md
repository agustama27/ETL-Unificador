# Design: Implement Naranja X MA Voice PCT

## Decisions

### D1 — Stateless flag lives on the adapter, not the catalog

`MaVoicePctAdapter.stateful = False`; `MaChatAdapter`/`MaVoiceAdapter` gain
`stateful = True`. The service reads the flag exactly like the existing
`requires_state_change` precedent. Widening the catalog schema is deferred
until a second stateless ETL exists; the adapter already owns the other
state-adjacent flag, so cohesion improves rather than degrades.

### D2 — Service skips the three state interactions when stateless

In `RunService.execute`, when `adapter.stateful` is false:

- `_state_preflight` is skipped (no lineage can ever gate a stateless run),
- `_stage_current` is skipped (nothing canonical to copy),
- promotion is skipped; `postconditions.state` records `not_applicable` and
  `state.status` remains `not_started`.

The ETL/month lock is still acquired: it is cheap, prevents concurrent PCT
runs from racing the same output window, and keeps one code path for locking.

### D3 — Staged destination derives its suffix from the validated source

`_stage_inputs` maps `base -> input/base{suffix}` where the suffix already
passed the catalog extension gate. Chat and Voice specs only allow `.xlsx`, so
their staged name is provably unchanged; PCT declares `.csv` and stages
`input/base.csv`. Adapters keep hardcoding their staged path because the spec
pins the only admissible suffix per ETL.

### D4 — Command is minimal and explicit

```text
<active python> back-resultados/etl_tipificaciones_ia_voz_pct.py
  --input <run>/input/base.csv
  --output_dir <run>/output
```

`--input` is always passed to disable the legacy `roman/` autodetection.
`--log_level` is not exposed: INFO is the legacy default and evidence captures
stderr regardless. cwd is the catalog `working_dir` (subproject root).

### D5 — Output classification reuses the shared classifier

New `ArtifactRole.PCT = "pct"`; catalog output
`{role: pct, glob: 'NARANJAX_PCT_*.csv', date_format: YYYYMMDD}` with
`output_date_source: system_date`. The adapter delegates to the shared
`MaChatAdapter.outputs` role loop, which already enforces
missing/ambiguous/wrong-date/unchanged per role.

### D6 — Validation set for a stateless job

- `business_date` must equal host-local today (shared gate — output name uses
  the machine date).
- `planes`, `pagos`, and `no_planes_today` must be absent/false: PCT has no
  daily inputs, and accepting them silently would fabricate intent.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Catalog `stateful` field | Schema churn for one consumer; revisit with MT |
| Empty staged state for PCT | Fabricates state evidence |
| PCT-specific service | Duplicates the verified lifecycle |
| Exposing `--log_level` | Adds surface without operational need |

## Test Strategy

- Adapter unit tests: exact command, today gate, daily-intent rejection.
- Service tests: stateless run skips preflight/staging/promotion, keeps lock,
  records `not_applicable`; stateful regression pinned.
- Catalog tests: PCT executable with complete metadata; MT still inert.
- Synthetic CLI E2E: success writes `NARANJAX_PCT_<today>.csv` evidence with no
  state lineage; failure modes (nonzero, timeout, spawn, missing output,
  ambiguous output) preserve evidence; redaction holds.
