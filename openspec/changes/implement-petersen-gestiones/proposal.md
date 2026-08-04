# Proposal: Implement Petersen Gestiones (AG002)

## Intent

Catalog the seventh and last client. Contrary to the initial assumption, the
Petersen `main.py` pipeline is fully LOCAL: it transforms ROMAN exports into
per-bank tipification files, validates promesas, applies the approach merge,
and ships `Gestiones_Petersen_YYYYMMDD.zip` with the four AG002 files. Only
the auxiliary Retell enrichment (`test_retell_api.py` scope) needs the API.

## Contract Evidence

The repo only had a Retell API test. This change adds wrapper subprocess
tests driving the REAL pipeline with a synthetic ROMAN export (the
`[Salida]`/`[Entrada]`-prefixed column contract, utf-8-sig, one valid
promesa per bank): complete four-bank ZIP on success, fail-fast without
publishing when a bank file is missing.

## Approach

- Every legacy folder resolves through `procesos.paths.get_project_root()` —
  the wrapper repoints that module-`__file__` seam at a sandbox work root,
  stages ROMAN plus the optional approach/base/excluidos inputs into the
  legacy layout, runs the exact legacy `main()` fail-fast, and publishes the
  ZIP into `output/`.
- New `PetersenGestionesAdapter`: stateless, today-only, optional extras
  gate (`approach`/`clientes`/`excluidos` forwarded as explicit flags via
  the multi-input contract), plus the `gestiones` artifact role.
- `registry/petersen.yaml` also inventories `petersen.retell` as blocked.

## Delivery and Evidence

- Full unifier suite: **272 passed**.
- Real platform run (fecha 20260804, synthetic ROMAN): `status=succeeded`,
  `Gestiones_Petersen_20260804.zip` evidenced containing exactly
  `AG002_45..48.csv`, `state: not_applicable`.

## Out of Scope

Retell enrichment, real data, UAT.
