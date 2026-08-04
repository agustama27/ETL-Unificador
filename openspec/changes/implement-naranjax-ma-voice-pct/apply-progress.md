# Apply Progress: Implement Naranja X MA Voice PCT

## Status

Complete — single slice implemented and verified synthetically plus one real
fixture-driven platform run.

## Completed Units

| Unit | Result |
|---|---|
| 1.1 RED | New adapter suite, stateless service test, and catalog promotion assertions written first; failures were assertion-driven |
| 1.2 GREEN | `MaVoicePctAdapter`, `ArtifactRole.PCT`, `stateful` flags with service skip branch, suffix-preserving staging, catalog promotion, CLI registration |
| 1.3 RED/GREEN | Synthetic `pct` channel and CLI E2E lifecycle (success, non-today, nonzero, timeout, spawn, missing, ambiguous) |
| 1.4 VERIFY | Full suite 147 passed; legacy contract suite 27 passed untouched; plan doc updated; `var/` runtime evidence ignored |

## Evidence

- `python -m pytest tests -q` → **147 passed**.
- `python -m pytest back-resultados/tests -q` (in `soho-naranjaX-MA-etl`) →
  **27 passed** (unchanged by this slice).
- Real platform run with the committed synthetic fixture
  `historial_minimo.csv`: `status=succeeded`, artifact
  `output/NARANJAX_PCT_20260804.csv` (`|`, cp1252, 7 columns), postconditions
  `{"outputs": "passed", "state": "not_applicable"}`, no `estado_*.csv`
  created anywhere under `var/state/`.

## Notes

- The ETL/month lock still creates the lineage directory (by design, D2);
  no state files are ever written for stateless runs.
- `.gitignore` now excludes `var/` so runtime evidence cannot be committed.
