# Design: Implement Remaining Tipificaciones PCT Jobs

## Decisions

### D1 — Catalog-only promotion; the adapter is already the product

`MaVoicePctAdapter` reads every job-specific fact from the catalog definition
(entry point, output glob, date format). Chat PCT's entry point is
byte-identical to MA Voice PCT's; MT PCT differs only in output naming. Two
new entries reuse the class under keys `naranjax.ma.chat.pct` and
`naranjax.mt.voice.pct` with per-entry instances, exactly like the existing
registration pattern. Renaming the class to `TipificacionesPctAdapter` is
deliberate future churn, not part of this change.

### D2 — MT PCT keeps the `pct` role with a `.txt` glob

The classifier is glob-driven; `DEELO_NAR_USUEVOLTIS_*.txt` with `YYYYMMDD`
matches the legacy `%Y%m%d` filename. No enum change. The `--back` job also
emits `DEELO_NAR_USUEVOLTIS_*` — irrelevant here because each run's diff only
sees its own sandbox `output/`.

### D3 — One implementation slice

Registry (+~36), CLI registration (+4), catalog test, adapter-stub updates,
one parametrized E2E file, docs/SDD close — comfortably under 400 lines.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| New adapter subclass per job | No behavioral difference to encode |
| Generic rename now | Churn without behavior; noted for later |
| Folding MT `--back` into this change | No legacy contract suite; needs multi-input core design |

## Test Strategy

- Catalog: six executable entries, each with complete metadata and its own
  adapter key; loading fails if any key is unregistered.
- E2E (parametrized over both new entries): CLI selection, success with the
  correct artifact name and `state: not_applicable`, non-today block, nonzero
  exit, missing output, no state lineage, redaction.
- Real verification: one platform run per entry with committed legacy synthetic
  fixtures (Chat) and a generated tipificaciones CSV (MT).
