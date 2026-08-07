# Tests del cliente

Copiá `etls/petersen/tests/` como referencia:

- `test_<cliente>_base.py` — e2e sintético vía `orchestrator.run.main` con
  `SyntheticRunner` (sin legacy real ni datos de producción). Debe cubrir succeeded /
  nonzero_exit / postcondition_failed / validation_error, y snapshot_exists si es stateful.
- `test_<cliente>_job.py` — sólo si escribiste `job.py`: corre el wrapper como subprocess
  contra el legacy real con una fixture mínima inventada.
