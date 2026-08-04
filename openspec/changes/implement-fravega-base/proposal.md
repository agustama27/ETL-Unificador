# Proposal: Implement Fravega Base (back-base)

## Intent

Catalog the fourth non-Naranja X client. Fravega back-base cleans the raw
cobranzas CSV (`;`-delimited): drops negative "Dias atraso" rows, prefixes
"Cel" with `+549`, and emits the fixed-name `fravega_base.csv`.

## Contract Evidence

The repo had ZERO tests. This change adds the first coverage: an additive
contract suite in `back-base/tests/` driving the real `clean_base` (filtering,
`+549` prefix, `;` output, required-column and missing-input failures) — now
**3 passed** — plus wrapper subprocess tests in the unifier.

## Approach

- `clean_base` already takes explicit `input_dir`/`output_dir`/
  `output_filename` — the wrapper (`adapters/fravega/base_job.py`) stages the
  input and writes the dateless fixed-name output (role `base_filtrada`)
  straight into the run `output/`, fail-fast.
- `registry/fravega.yaml` also inventories `fravega.resultados.retell` as
  blocked (Retell.ai manager — API and credentials required).

## Delivery and Evidence

- Full unifier suite: **252 passed**.
- Real platform run (fecha 20260804, synthetic CSV): `status=succeeded`,
  `fravega_base.csv` evidenced with the negative-atraso row dropped and
  `+549` prefix applied, `state: not_applicable`.

## Out of Scope

Retell results execution, real data, UAT.
