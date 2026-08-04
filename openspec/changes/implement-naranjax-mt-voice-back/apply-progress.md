# Apply Progress: Implement Naranja X MT Voice Back (USUEVOLTIS)

## Status

Complete — contract suite, multi-input core, and back promotion delivered in
three slices plus one real fixture-driven platform run.

## Completed Units

| Unit | Result |
|---|---|
| Contract suite (#56) | Additive legacy suite pinning the USUEVOLTIS contract (MT back-resultados 10 passed) |
| PR1 (#60) | `RunRequest.extras`, truthful role staging, CLI `--input ROLE=PATH`, `anomalies` role, extras rejection in all four prior adapters |
| PR2 | `MtVoiceBackAdapter`, seventh catalog entry, dual-output classification, synthetic E2E, SDD close |

## Evidence

- `python -m pytest tests -q` → **220 passed**.
- MT legacy suite untouched by PR2: **10 passed**.
- Real platform run (fecha 20260804, synthetic fixtures): `status=succeeded`;
  staged inputs `input/base.txt`, `input/logcall.csv`, `input/historial.csv`;
  artifacts `DEELO_NAR_USUEVOLTIS_20260804_02.txt` (40 columns, CRLF, col 8
  `USUEVOLTIS`) and `_anomalias_20260804_021423.txt`; postconditions
  `{"outputs": "passed", "state": "not_applicable"}`; no state lineage.

## Notes

- USUEVOLTIS carries the `pct` role (same tipificaciones-artifact family as
  MT PCT); the anomalies report has its own `anomalies` role.
- Strict-phone-quality knobs are not exposed; legacy defaults apply.
