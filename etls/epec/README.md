# EPEC

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `epec.base.daily` | ✅ operativo | Base consolidada → ROMAN + E1KIA |
| `epec.tipif.retell` | ⛔ inerte | Tipificaciones Retell.ai — espera API y credenciales |

## Contrato

- Entrada `base` (`.csv`, requerida) → salidas `roman` (`EPEC_ROMAN_YYMMDD.csv`) y
  `e1kia` (`EPEC_E1KIA_YYMMDD.csv`).
- Adapter: `SubprocessAdapter` genérico (`etl_core`). Sin estado mensual.

## Estructura

`manifest.yaml` · `job.py` · `legacy/` (no tocar) · `tests/` (e2e sintético + job test
contra el legacy real).

## Contacto

Equipo de operaciones Evoltis (canal EPEC). Sin deadline formal declarado.
