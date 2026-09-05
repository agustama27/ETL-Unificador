# Verificación de fidelidad — migración Fase 3 (registry/ → etls/)

La Fase 3 del ADR-001 se consolidó en un solo PR con un commit por unidad, en vez del
PR-por-cliente que sugería el plan. Esta verificación reemplaza la garantía que ese flujo
habría dado: comparación automatizada, campo por campo, de los 22 ETLs entre el
`registry/<cliente>.yaml` previo a la migración (ref `f0313d6`, tip de la Fase 2) y el
`etls/<cliente>/manifest.yaml` migrado.

- **Herramienta:** `scripts/compare_manifests.py` (reproducible:
  `python scripts/compare_manifests.py f0313d6`)
- **Campos comparados:** `id`, `command`, `fixed_arguments`, `arguments`,
  `inputs` (role + extensions + required), `outputs` (role + glob + **date_format**),
  `allowed_exits`, `timeout_seconds`, `request_date_format`, `output_date_source`,
  `environment_allowlist`, clase de adapter y `stateful`.
- **Publicada originalmente** como comentario en el PR #94 (cerrado sin mergear durante la
  recuperación de la cadena; ver PR #99).

## Resultado: 22/22 comparados — única diferencia: `command` en los 9 ETLs con wrapper

| ETL | Diferencia |
|---|---|
| `naranjax.ma.chat.daily` · `ma.voice.daily` · `ma.voice.pct` · `ma.chat.pct` · `mt.voice.pct` · `mt.voice.back` | idénticos en todos los campos |
| `bancor.resultados.retell` · `bancor.carga_masiva` · `bancor.cupones` · `petersen.retell` · `epec.tipif.retell` · `fravega.resultados.retell` · `clarouy.encuestas.retell` (inertes) | idénticos en todos los campos |
| `encuestacx.base.daily` | idéntico en todos los campos salvo `command` |
| `naranjax.mt.voice.daily` | `command`: `../adapters/naranjax/mt_voice_job.py` → `../../mt_voice_job.py` |
| `bancor.base.daily` | `command`: `../adapters/bancor/base_job.py` → `../job.py` |
| `petersen.gestiones.daily` | `command`: `../adapters/petersen/gestiones_job.py` → `../job.py` |
| `epec.base.daily` | `command`: `../adapters/epec/base_job.py` → `../job.py` |
| `fravega.base.daily` | `command`: `../adapters/fravega/base_job.py` → `../job.py` |
| `clarouy.base.daily` | `command`: `../adapters/clarouy/base_job.py` → `../job.py` |
| `social.argentina.base` · `social.chile.base` | `command`: `../adapters/sociallearning/base_job.py` → `../job.py` |

Los cambios de `command` son la reubicación intencional de los wrappers `job.py` dentro
de cada paquete de cliente (el comando es relativo al `working_dir`, que pasó a
`etls/<cliente>/legacy`). Los campos de ruta `project_path`/`working_dir`/`entrypoint`
cambiaron por diseño en la misma dirección y no forman parte del contrato de ejecución.

## `date_format`: cero diferencias en los 22

Era el campo de mayor riesgo (un error se descubre el día de la entrega). Se preservaron
incluso las combinaciones mixtas dentro de un mismo ETL:

- `naranjax.ma.chat.daily`: `roman:YYYYMMDD` + `chat:YYMMDD` + `e1kia:YYMMDD`
- `bancor.base.daily`: `base_filtrada`/`telefonos` en `DDMMYYYY` + `roman`/`e1kia` en `YYYYMMDD`
- `epec.base.daily`: `YYMMDD` · `clarouy.base.daily`: `DDMMYYYY`

`stateful` idéntico (sólo `MaChatAdapter` y `MaVoiceAdapter` son `True`).

## Verificación complementaria (UAT, 2026-08-07)

Equivalencia byte a byte producción (legacy standalone) vs plataforma, con datos reales:

- **Petersen**: 4/4 `AG002_*.csv` idénticos (sha256).
- **Naranja X MA Chat**: `ROMAN` + `CHAT` + `E1KIA` + `estado_YYYYMMDD` + `estado_YYYYMM`
  — 5/5 idénticos (sha256), base real de 2298 filas, modo `no_planes_today`.
