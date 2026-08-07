# Frávega

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `fravega.base.daily` | ✅ operativo | Base de cobranzas filtrada (`fravega_base.csv`) |
| `fravega.resultados.retell` | ⛔ inerte | Resultados Retell.ai — espera API y credenciales |

## Contrato

- Entrada `base` (`.csv`, requerida) → salida `base_filtrada` (`fravega_base.csv`, sin fecha en nombre).
- Adapter: `SubprocessAdapter` genérico (`etl_core`). Sin estado mensual.

## Estructura

`manifest.yaml` · `job.py` · `legacy/` (no tocar) · `tests/` (e2e sintético).

## Contacto

Equipo de operaciones Evoltis (canal Frávega). Sin deadline formal declarado.
