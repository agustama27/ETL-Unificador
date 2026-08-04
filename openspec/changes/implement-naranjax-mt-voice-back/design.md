# Design: Implement Naranja X MT Voice Back (USUEVOLTIS)

## Decisions

### D1 — `extras` extends `RunRequest`; roles stay catalog data

`RunRequest.extras: Mapping[str, Path]` (immutable, default empty), populated
by repeatable CLI `--input ROLE=PATH`. `_stage_inputs` resolves sources as
`{base, planes, pagos} | extras` and derives unknown-role destinations as
`input/<role><suffix>` — the same suffix-preserving rule the base input
already follows. Catalog input specs (`role`, `extensions`, `required`)
already model arbitrary roles; no schema change.

### D2 — Required-extra enforcement lives in staging plus adapter

Staging skips undeclared roles (catalog is the allowlist) and the existing
required-input semantics apply. The back adapter additionally validates that
exactly `{logcall, historial}` extras are present so a missing file fails as
`validation_error` before lock/subprocess. Daily adapters gain one guard:
requests carrying extras are rejected (no silent ignoring).

### D3 — Exact back command

```text
<active python> main.py --back
  --logcall <run>/input/logcall.csv
  --historial <run>/input/historial.csv
  --m30 <run>/input/base.txt
  --back-output-dir <run>/output
```

Strict-quality knobs are not exposed; legacy defaults apply.

### D4 — `anomalies` role; hour-stamped names ride the YYYYMMDD check

`ArtifactRole.ANOMALIES = "anomalies"`. Globs `DEELO_NAR_USUEVOLTIS_*.txt`
and `_anomalias_*.txt` with `date_format: YYYYMMDD`: both filenames embed
`%Y%m%d` followed by `_`, which satisfies the boundary-guarded date regex.

### D5 — Two slices

Slice 1 (core): extras model/staging/CLI + anomalies role + tests.
Slice 2 (adapter): back adapter, catalog entry, E2E, real run, SDD close.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Reuse planes/pagos fields for logcall/historial | Evidence lies |
| Per-ETL CLI flags | Erodes the generic CLI |
| Anomalies as legacy_log | It is a contract artifact, not a log copy |

## Test Strategy

- Core: extras staging (truthful names, hashes, extension gate), CLI parsing
  (repeatable, malformed rejected), daily-adapter extras rejection.
- Adapter: exact command, extras completeness, today gate, dual-output
  classification.
- E2E: success (both artifacts, `state: not_applicable`), non-today, missing
  extra, nonzero, missing output; redaction; no lineage.
- Real run with the synthetic fixtures from the #56 contract suite.
