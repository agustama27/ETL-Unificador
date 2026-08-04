# Apply Progress: Implement Remaining Tipificaciones PCT Jobs

## Status

Complete — catalog-only promotion implemented and verified synthetically plus
one real fixture-driven platform run per new entry.

## Completed Units

| Unit | Result |
|---|---|
| Docs PR (#52) | SDD artifacts for the change |
| Feat PR | Two catalog entries, two CLI adapter keys (reusing `MaVoicePctAdapter`), six-entry catalog assertions, parametrized synthetic E2E, adapter-stub updates |

## Evidence

- `python -m pytest tests -q` → **184 passed**.
- Legacy suites untouched: Chat back-resultados **25 passed**; MT
  back-resultados **7 passed**.
- Real platform runs (fecha 20260804):
  - `naranjax.ma.chat.pct` with the committed Chat synthetic fixture →
    `NARANJAX_PCT_20260804.csv` (`|`, cp1252, 7 columns), state
    `not_applicable`, no lineage.
  - `naranjax.mt.voice.pct` with a generated (non-committed) tipificaciones
    CSV → `DEELO_NAR_USUEVOLTIS_20260804.txt` (`|`, cp1252, 40 columns, col 8
    `USUEVOLTIS`, col 36 `EVOLTIS`), state `not_applicable`, no lineage.

## Notes

- Zero new adapter code: both entries resolve `MaVoicePctAdapter` instances;
  every job-specific fact (entry point, glob, date format) is catalog data.
- MT `--back` remains the only legacy job outside the catalog (own change).
