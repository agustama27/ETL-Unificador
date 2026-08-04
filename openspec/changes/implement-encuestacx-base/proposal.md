# Proposal: Implement Encuesta CX Base (multi-client pilot)

## Intent

Catalog the first non-Naranja X client. Encuesta CX transforms a survey Excel
into two fixed-name CSVs (`base_encuesta.csv`, `base_encuesta_e164.csv`)
consumed by the n8n/Retell workflow.

## Contract Evidence

- Legacy suite green after #68: **36 passed** (transformer tests realigned to
  the n8n 15-column contract — `Status de encuesta`, `phone number`).
- The n8n workflow reference (`ENCUESTA-inbound-wh.json`) is the arbiter for
  column naming.

## Approach

- Legacy `main.py` takes no arguments and anchors every path to the repo; the
  unifier ships `adapters/encuestacx/base_job.py`, which repoints the shared
  config singleton (INPUT_FILE, OUTPUT_DIR/FILES, LOG_DIR) at the staged
  input and run sandbox, then runs the exact legacy `main()` (exit 0/1).
- Stateless single-input entry reusing the generic stateless job adapter
  (`--input`/`--output_dir`, staged `input/base.xlsx` from the catalog
  extension spec).
- Outputs are dateless by contract (n8n consumes stable names) — modeled with
  the optional `date_format` core contract (#70) and the
  `survey_base`/`survey_base_e164` roles.

## Delivery and Evidence

Chain: contract fix #68 → dateless-output core #70 → this slice (wrapper,
`registry/encuestacx.yaml`, CLI key, wrapper subprocess tests against the
real pipeline with a synthetic Excel, synthetic E2E, one real platform run).

- Full unifier suite: **231 passed**.
- Real run (fecha 20260804, synthetic Excel): `status=succeeded`, both CSVs
  evidenced (`survey_base`, `survey_base_e164`), `state: not_applicable`,
  normalized phone `5493517710632` / `+5493517710632`.

## Out of Scope

Real survey data, n8n/Retell execution, UAT; `back-resultados` (empty in the
legacy repo — future job).
