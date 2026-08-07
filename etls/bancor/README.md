# Bancor

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `bancor.base.daily` | ✅ operativo | Base de llamadas → filtrada + teléfonos + ROMAN + E1KIA |
| `bancor.resultados.retell` | ⛔ inerte | Resultados Retell.ai — espera API y credenciales |
| `bancor.carga_masiva` | ⛔ inerte | Carga masiva CRM — diseño pendiente |
| `bancor.cupones` | ⛔ inerte | Cupones de pago — legacy VBA en desarrollo |

## Contrato

- Entrada `base` (`.csv`, requerida) → salidas `base_filtrada` y `telefonos`
  (`con-filtros/`, fecha DDMMYYYY) + `roman` y `e1kia` (`sin-filtros/`, fecha YYYYMMDD).
- Adapter: `SubprocessAdapter` genérico (`etl_core`). Sin estado mensual.

## ⚠️ Punto frágil conocido

`job.py` reasigna el `__file__` de `procesos.base_generator` para anclar el `base_dir`
del legacy al sandbox (ver `docs/ARQUITECTURA.md` §6). Depende del `cwd` y de que el
legacy siga derivando rutas de `__file__`. **No copiar este patrón en jobs nuevos.**

## Deadline y contacto

- **Entrega miércoles y viernes antes de 12:30.**
- Equipo de operaciones Evoltis (canal Bancor).
