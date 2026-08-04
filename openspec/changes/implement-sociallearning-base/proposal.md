# Proposal: Implement Social Learning Bases (Argentina + Chile)

## Intent

Catalog the sixth non-Naranja X client with two country entries:
`social.argentina.base` (`SOCIAL_ARG_CARTERA_YYYYMMDD.csv`) and
`social.chile.base` (`SOCIAL_CHI_CARTERA_YYYYMMDD.csv`).

## Contract Evidence

The repo had no pytest coverage (only a manual smoke harness). This change
adds the first suite: contract tests driving both real `generate_base`
functions through their explicit-path seam (country-specific input columns,
derived output schema, headerless failure) — now **3 passed**.

## Approach

- Both generators already accept explicit `input_path`/`output_path`; one
  shared wrapper (`adapters/sociallearning/base_job.py --country
  argentina|chile`) selects the country module and writes the dated legacy
  filename straight into the sandbox `output/`, fail-fast.
- Core: the generic stateless job adapter now forwards catalog
  `fixed_arguments` in its command — behavior-identical for every existing
  entry (all had `[]`) and pinned by the existing command-exactness suites.
- IDs use the short `social.*` prefix: the longer `sociallearning.*` ids
  pushed sandboxed artifact paths past Windows MAX_PATH.

## Delivery and Evidence

- Full unifier suite: **267 passed**.
- Real platform runs (fecha 20260804, synthetic CSVs): both countries
  `status=succeeded` with their dated artifact evidenced,
  `state: not_applicable`.

## Out of Scope

Real data, UAT.
