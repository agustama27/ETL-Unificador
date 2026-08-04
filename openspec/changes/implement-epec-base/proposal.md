# Proposal: Implement EPEC Base (back-base)

## Intent

Catalog the third non-Naranja X client. EPEC back-base consolidates raw
suministro CSVs into `EPEC_ROMAN_YYMMDD.csv` and the phone extract
`EPEC_E1KIA_YYMMDD.csv`.

## Contract Evidence

- Legacy suite green as found: **7 passed** (`back-base/tests`, run from the
  module cwd).
- Wrapper subprocess tests drive the real chain with a synthetic CSV
  (required columns SUMINISTRO/CONTRATO/RAZON_SOCIAL/BARRIO/DIRECCION/
  FECHA_EJECUCION/TELEFONO/TELEFONO_CELULAR plus MOTIVO), including the
  missing-required-column failure path.

## Approach

- Legacy `main()` anchors its root to the module file, but every helper takes
  `carpeta_base` as a parameter — the cleanest seam so far. The wrapper
  (`adapters/epec/base_job.py`) runs the exact chain (`combinar_archivos` →
  `guardar_csv_consolidado` → `generar_csv_telefonos`) against a
  sandbox-rooted layout, fail-fast, publishing `base-generada/*.csv` (not
  `debug/`) into `output/`.
- Stateless single-input entry reusing the generic stateless job adapter;
  outputs `YYMMDD` roman/e1kia roles.
- `registry/epec.yaml` also inventories `epec.tipif.retell` as blocked: the
  repo-root `main.py` is the Retell.ai enrichment/tipification CLI (API and
  credentials required — same category as Petersen and bancor.resultados).

## Delivery and Evidence

- Full unifier suite: **247 passed**.
- Real platform run (fecha 20260804, synthetic CSV): `status=succeeded`,
  `EPEC_ROMAN_260804.csv` + `EPEC_E1KIA_260804.csv` evidenced,
  `state: not_applicable`, no legacy residue.

## Out of Scope

Retell enrichment execution, real data, UAT.
