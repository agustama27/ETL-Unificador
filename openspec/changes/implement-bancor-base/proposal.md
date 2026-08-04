# Proposal: Implement Bancor Base (back-base)

## Intent

Catalog the second non-Naranja X client. Bancor back-base cleans the raw
client CSV into the calling base (con-filtros), the complete ROMAN base
(sin-filtros), and their phone extracts.

## Contract Evidence

- Bancor's own suites green as found: **49 passed** (quita, phone
  normalization, phone compare, WFM exports).
- Wrapper subprocess tests drive the real four-step pipeline with a synthetic
  `;`-delimited latin-1 CSV (ModuloCodigo `201` filter, `OFERTA_Importe > 0`).

## Approach

- Legacy `main.py` takes no arguments, anchors paths to the module file, and
  swallows step failures. The unifier ships `adapters/bancor/base_job.py`:
  anchors the pipeline to the run sandbox via the `base_generator.__file__`
  seam, pre-creates the legacy directory layout, runs the exact four-step
  chain **fail-fast**, and publishes `base-generada/**` into `output/`
  preserving the `con-filtros`/`sin-filtros` split.
- Core additions: `DDMMYYYY` output date format (legacy `%d%m%Y` names) and
  `base_filtrada`/`telefonos` artifact roles.
- Stateless single-input entry reusing the generic stateless job adapter.
- `registry/bancor.yaml` also inventories the three remaining Bancor modules
  as inert with documented reasons: `bancor.resultados.retell` (blocked —
  requires the Retell.ai API and credentials, same category as Petersen),
  `bancor.carga_masiva` (candidate — design pending), `bancor.cupones`
  (blocked — legacy still in development).

## Delivery and Evidence

- Full unifier suite: **239 passed** (wrapper subprocess tests, four-artifact
  postconditions with mixed date formats, synthetic E2E lifecycle).
- Real platform run (fecha 20260804, synthetic CSV): `status=succeeded`, all
  four artifacts evidenced, `state: not_applicable`, no legacy residue.
- Gotcha pinned during verification: Windows MAX_PATH — long pytest tmp paths
  broke the longest artifact name; E2E uses shortened run dirs.

## Out of Scope

Retell-dependent modules execution, real data, UAT.
