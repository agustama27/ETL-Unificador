# Petersen

Paquete autocontenido del cliente Petersen (ADR-001, decisión 5).

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `petersen.gestiones.daily` | ✅ operativo | Gestiones AG002 desde export ROMAN → ZIP con un CSV por banco |
| `petersen.retell` | ⛔ inerte | Enriquecimiento Retell.ai — espera API y credenciales |

## Entradas

- `base` (`.csv`, requerida): export ROMAN de gestiones del día
- `approach` (`.csv`, opcional) · `clientes` (`.csv`, opcional) · `excluidos` (`.csv`, opcional)

## Salidas

- `gestiones`: `Gestiones_Petersen_YYYYMMDD.zip` con `AG002_45..48.csv` (uno por banco:
  Santa Fe, Entre Ríos, Santa Cruz, San Juan)

## Estructura

- `manifest.yaml` — declaración del catálogo
- `adapter.py` — `PetersenGestionesAdapter` (compone `SubprocessAdapter` para postcondiciones)
- `job.py` — CLI puente: ancla `procesos.paths` del legacy al sandbox y ejecuta `main()` fail-fast
- `legacy/` — proyecto original (NO tocar: reglas de negocio en producción)
- `tests/` — e2e sintético + test del job contra el legacy real

## Reglas de negocio (viven en `legacy/`, no acá)

Tipificación de gestiones por efecto/promesa, partición por banco gestionado, reglas en
`legacy/docs/REGLAS_TIPIFICACIONES.md`.

## Deadline y contacto

- Sin deadline formal declarado (correr con la base del día).
- Contacto de negocio: equipo de operaciones Evoltis (canal de cobranzas Petersen).
