# Proposal: Multi-Client Catalog

## Intent

Unblock onboarding of the seven non-Naranja X clients (Bancor, ClaroUY,
encuestaCX, EPEC, Frávega, Petersen, socialLearning): the CLI hardcoded
`registry/naranjax.yaml`, so no other client could be cataloged.

## Scope

### In Scope
- `Catalog.load_directory(directory, workspace, adapters)`: load every
  `registry/*.yaml` in filename order with the existing per-file validation
  and reject duplicate ETL ids across files.
- CLI loads the registry directory instead of the single Naranja X file.
- One combined docs+code slice below 400 lines.

### Out of Scope
- Any new client entry (each client gets its own SDD chain).
- Schema changes; per-file rules are untouched.

## Approach and Design

`load_directory` composes the verified `load`: same schema, same containment,
same executable gates. Merge-time invariant: global id uniqueness (per-file
uniqueness already enforced). Filename ordering keeps catalog listing
deterministic. Behavior with only `naranjax.yaml` present is provably
identical — the repository-level test pins the seven existing entries.

## Success Criteria

- [x] Two catalog files merge deterministically; cross-file duplicate ids and
      empty directories are rejected.
- [x] Repository registry loads the seven Naranja X entries unchanged
      (full suite 223 passed).

## Delivery

Single slice: `feat(orchestrator): load all client catalogs from registry`.
Rollback: revert the slice; the CLI returns to the single-file load.
