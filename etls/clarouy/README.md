# Claro Uruguay

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `clarouy.base.daily` | ✅ operativo | Base de encuestas + teléfonos por cliente |
| `clarouy.encuestas.retell` | ⛔ inerte | Encuestas desde Retell.ai — espera API y credenciales |

## Contrato

- Entrada `base` (`.csv`, requerida) → salidas `base_filtrada` (`base_clarouy_DDMMYYYY.csv`)
  y `telefonos` (`telefonos_x_cliente_DDMMYYYY.csv`).
- Adapter: `SubprocessAdapter` genérico (`etl_core`). Sin estado mensual.

## Estructura

`manifest.yaml` · `job.py` · `legacy/` (no tocar; contiene el proyecto anidado
`soho-clarouy-encuestas-etl`) · `tests/` (e2e sintético).

## Contacto

Equipo de operaciones Evoltis (canal Claro UY). Sin deadline formal declarado.
