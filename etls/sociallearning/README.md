# Social Learning

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `social.argentina.base` | ✅ operativo | Cartera Argentina (`SOCIAL_ARG_CARTERA_YYYYMMDD.csv`) |
| `social.chile.base` | ✅ operativo | Cartera Chile (`SOCIAL_CHI_CARTERA_YYYYMMDD.csv`) |

## Contrato

- Entrada `base` (`.csv`, requerida) → salida `base_filtrada` por país.
- El país viaja como `fixed_arguments: [--country, argentina|chile]` en el manifiesto —
  mismo `job.py` para ambos.
- Adapter: `SubprocessAdapter` genérico (`etl_core`). Sin estado mensual.

## Estructura

`manifest.yaml` · `job.py` · `legacy/` (no tocar; proyecto anidado
`soho-social-learning-etl` con `base_argentina/` y `base_chile/`) · `tests/` (e2e sintético).

## Contacto

Equipo de operaciones Evoltis (canal Social Learning). Sin deadline formal declarado.
