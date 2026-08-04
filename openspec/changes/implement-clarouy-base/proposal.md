# Proposal: Implement ClaroUY Base (back-base)

## Intent

Catalog the fifth non-Naranja X client. ClaroUY back-base consolidates the
raw clients CSV into the deduplicated `base_clarouy_DDMMYYYY.csv` and the
`telefonos_x_cliente_DDMMYYYY.csv` extract used to load Retell campaigns.

## Contract Evidence

The repo had ZERO tests. This change adds the first coverage: an additive
contract suite in `back-base/tests/` driving the real chain
(`procesar_base`, `deduplicar_por_telefonos`, `buscar_base_generada`,
`extraer_telefonos`) — now **2 passed** — plus empirical wrapper execution.

## Approach

- The legacy functions are fully parameterized; the wrapper
  (`adapters/clarouy/base_job.py`) mirrors the exact `main()` chain against
  sandbox folders, fail-fast, publishing both dated artifacts (`DDMMYYYY`,
  roles `base_filtrada`/`telefonos`) into `output/`.
- `registry/clarouy.yaml` also inventories `clarouy.encuestas.retell` as
  blocked (Retell.ai encuestas generator — API and credentials required).

## Delivery and Evidence

- Full unifier suite: **257 passed**.
- Real platform run (fecha 20260804, synthetic CSV): `status=succeeded`,
  both artifacts evidenced, `state: not_applicable`.

## Out of Scope

Retell encuestas execution, real data, UAT.
