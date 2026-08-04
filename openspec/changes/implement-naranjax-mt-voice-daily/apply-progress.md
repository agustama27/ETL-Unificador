# Apply Progress: Implement Naranja X MT Voice Daily

## Status

Complete — two slices implemented and verified synthetically plus one real
fixture-driven platform run.

## Completed Units

| Unit | Result |
|---|---|
| PR1 (#48) | `mt_voice_job.py` wrapper, stateless `MtVoiceAdapter`, complete inert catalog metadata, wrapper subprocess tests against the real `procesos` modules |
| PR2 | Catalog promotion, CLI registration, synthetic MT E2E lifecycle, plan doc, SDD close |

## Evidence

- `python -m pytest tests -q` → **174 passed**.
- MT legacy suite untouched: `python -m pytest back-resultados/tests -q` → **7 passed**.
- Wrapper subprocess tests: valid 33-column TXT → ROMAN then E1KIA only in the
  sandbox; wrong column count / empty / missing input → exit 1 with the legacy
  stderr message.
- Real platform run with a generated (non-committed) synthetic TXT:
  `status=succeeded`, artifacts `NARANJAX_MT_ROMAN_260804.csv` and
  `NARANJAX_MT_E1KIA_260804.csv`, postconditions
  `{"outputs": "passed", "state": "not_applicable"}`, no `estado_*.csv`
  anywhere, and no residue in `back-base/base_procesada/`.

## Notes

- The inert-entry CLI test was repurposed: with zero inert entries left, it
  now proves an executable entry with an unregistered adapter fails at catalog
  load before any service is built.
- MT is the second stateless consumer; promoting the `stateful` flag into the
  catalog schema remains a future refactor option (PCT design D1).
