# _template — copiá esta carpeta para dar de alta un cliente

```bash
cp -r etls/_template etls/<cliente>
```

Flujo completo: `docs/GUIA_NUEVO_CLIENTE.md`. Resumen:

1. Respondé el relevamiento del Paso 0 de la guía y volcalo en este README.
2. Colocá el proyecto legacy en `legacy/` — **sin modificarlo**.
3. Completá `manifest.yaml` (los comentarios te guían campo por campo).
4. Si el legacy no tiene CLI usable, completá `job.py`; si necesita validaciones
   propias, completá `adapter.py`. Si acepta `--input`/`--output_dir`, borrá ambos y usá
   `adapter: etl_core.contracts:SubprocessAdapter`.
5. Escribí los tests en `tests/` copiando `etls/petersen/tests/` como referencia.
6. Registrá el nombre legible en `platform_api/catalog_meta.py::CLIENTS`.
7. `pytest` completo en verde y checklist del Paso 4 de la guía.

Las carpetas que empiezan con `_` no se cargan en el catálogo ni se ejecutan: esta
plantilla es inerte hasta que la copies con otro nombre.

---

## <Cliente> (reemplazá desde acá con el relevamiento real)

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `<cliente>.<proceso>.daily` | — | — |

## Entradas / Salidas

- `base` (`.csv`, requerida): …
- salida `<rol>`: `PATRON_*.csv` (fecha `YYYYMMDD`)

## Deadline y contacto

- Deadline: …
- Contacto de negocio: …
