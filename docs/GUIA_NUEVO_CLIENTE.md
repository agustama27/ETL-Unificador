# Guía — Cómo agregar un cliente nuevo

Procedimiento para integrar un ETL de un cliente nuevo a la plataforma. Describe el flujo
**vigente hoy**. Cuando se complete la Fase 3 del `ADR-001-nucleo-hexagonal.md`, los pasos 2 a 5
se reducen a "crear la carpeta `etls/<cliente>/`".

Lo primero: leé `docs/ARQUITECTURA.md`, en particular las secciones 5 (contrato de adapter) y 6
(puente con el legacy).

---

## Paso 0 — Relevar el ETL legacy

Antes de escribir una línea, respondé esto por escrito. Va a ser el `README.md` del cliente.

| Pregunta | Por qué importa |
|---|---|
| ¿Cuál es el entrypoint y qué argumentos acepta? | Define si necesitás un `*_job.py` |
| ¿Qué archivos de entrada requiere? ¿Cuáles son opcionales? | Va a `inputs` del manifiesto |
| ¿Qué archivos genera? ¿Con qué patrón de nombre y qué formato de fecha? | Va a `outputs`. Ojo: hay ETLs que mezclan `YYYYMMDD` y `YYMMDD` en la misma corrida |
| ¿Mantiene estado entre corridas? | Define `stateful` en el adapter |
| ¿Escribe logs propios? ¿Dónde? | El servicio los recoge de `logs/` y los normaliza |
| ¿Qué exit codes devuelve? ¿Devuelve `0` aunque falle? | Va a `allowed_exits`. Si el legacy se traga errores, las postcondiciones son tu única defensa |
| ¿Usa rutas relativas internas o derivadas de `__file__`? | Define si podés pasarle rutas por CLI o necesitás wrapper |
| ¿Cuánto tarda una corrida típica? | Va a `timeout_seconds`, con margen |
| ¿Cuál es el deadline operativo de entrega? | Va al README del cliente y a `DEADLINE_HINTS` |
| ¿Qué variables de entorno o credenciales necesita? | Va a `environment_allowlist` |

Si algo no se puede responder mirando el código, **preguntá antes de asumir**. Un supuesto
equivocado sobre el formato de fecha de un output se descubre recién en producción, el día de la
entrega.

---

## Paso 1 — Decidir el adapter

Tres caminos, en orden de preferencia.

### A. El legacy ya tiene CLI limpia → `SubprocessAdapter` genérico

Si acepta `--input` y escribe donde le decís, no escribas código. Sólo declaralo en el manifiesto
apuntando al adapter genérico. Es el caso de la mayoría de los clientes actuales.

### B. El legacy no tiene CLI usable → wrapper `*_job.py`

Escribí `adapters/<cliente>/<proceso>_job.py`: una CLI propia que recibe `--input` y `--output_dir`,
importa las funciones del legacy, las ejecuta en cadena fail-fast y copia los productos a
`output/`. Mirá `adapters/petersen/gestiones_job.py` como referencia limpia.

**No copies el patrón de `adapters/bancor/base_job.py`**, que reasigna el `__file__` de un módulo
importado. Funciona pero es frágil. Preferí, en este orden: pasar rutas por argumento → pasar rutas
por variable de entorno → como último recurso, monkeypatch documentado con un comentario que
explique por qué no había alternativa.

### C. Hay reglas de validación propias → adapter con clase

Sólo si el cliente tiene reglas específicas sobre qué combinación de entradas es válida, o
postcondiciones que el mecanismo genérico no cubre. Mirá `adapters/petersen/gestiones.py`:
declara extras opcionales y valida que no lleguen entradas de otro cliente.

**Regla dura:** el adapter valida forma, no negocio. Si estás escribiendo una regla de quita, un
filtro de módulos o un criterio de exclusión, eso va en el legacy, no acá.

---

## Paso 2 — Escribir el manifiesto

`registry/<cliente>.yaml`. Los campos y sus reglas de validación están en la sección 4 de
`docs/ARQUITECTURA.md`.

```yaml
schema_version: 1
etls:
  - id: micliente.base.daily
    name: Mi Cliente - Base diaria
    repository_status: present
    readiness: ready
    executable: true
    project_path: soho-micliente-etl
    working_dir: soho-micliente-etl
    entrypoint: adapters/micliente/base_job.py
    command: [python, ../adapters/micliente/base_job.py]
    fixed_arguments: []
    arguments:
      base: --input
    inputs:
      - {role: base, extensions: [.csv], required: true}
    outputs:
      - {role: roman, glob: 'MICLIENTE_ROMAN_*.csv', date_format: YYYYMMDD}
      - {role: e1kia, glob: 'MICLIENTE_E1KIA_*_sinestrategia.csv', date_format: YYMMDD}
    allowed_exits: [0]
    timeout_seconds: 900
    request_date_format: YYYYMMDD
    output_date_source: system_date
    adapter: micliente.base
```

### Convenciones

- **`id`:** `<cliente>.<canal o proceso>.<variante>`. Todo minúsculas, separado por puntos.
  El prefijo antes del primer punto se usa para agrupar por cliente en la UI.
- **`glob`:** relativo a `output/`, sin `..` ni rutas absolutas. Puede incluir subcarpeta
  (`con-filtros/base_*.csv`).
- **`date_format`:** sólo `YYYYMMDD`, `YYMMDD` o `DDMMYYYY`. Verificá el formato real de cada
  salida por separado; es común que difieran dentro del mismo ETL.
- **`timeout_seconds`:** duración típica con margen holgado. Un timeout corto genera falsos
  `timed_out`; uno largo deja el lock tomado más tiempo del necesario.
- **ETLs todavía no implementados:** declaralos con `executable: false` y el `readiness` que
  corresponda (`blocked` si depende de algo externo, `candidate` si falta diseño). Sólo necesitan
  `id`, `name`, `repository_status`, `readiness`, `executable` y `project_path`. Van a aparecer en
  el catálogo, deshabilitados. Agregá el motivo legible en `INERT_REASONS`
  (`platform_api/catalog_meta.py`) para que la UI lo muestre.

---

## Paso 3 — Registrar el cliente en el núcleo

> Estos tres puntos desaparecen con la Fase 1 y 2 del ADR-001. Hoy son obligatorios.

1. **`orchestrator/run.py`:** importar el adapter, agregarlo al alias de tipo `Adapter` y sumar la
   entrada al `dict` de `_adapters()`. La clave debe coincidir exactamente con el campo `adapter`
   del YAML.
2. **`orchestrator/models.py`:** si el cliente genera un tipo de artefacto nuevo, agregarlo al enum
   `ArtifactRole`. Si podés reusar un rol existente (`roman`, `e1kia`, `pct`, `gestiones`,
   `base_filtrada`, `telefonos`), reusalo.
3. **`platform_api/main.py`:** si el cliente pide un rol de archivo nuevo, agregarlo a `FILE_ROLES`.
   Si no, la API va a rechazar el upload con "El ETL no declara la entrada".
4. **`platform_api/catalog_meta.py`:** agregar el nombre legible del cliente a `CLIENTS`, más
   `INERT_REASONS` y `DEADLINE_HINTS` si corresponde.

---

## Paso 4 — Escribir los tests

### Test e2e (obligatorio)

Copiá `tests/e2e/test_petersen_gestiones.py` como plantilla. Tiene que cubrir:

- Corrida feliz: estado `succeeded`, artefactos presentes con el rol correcto, `run.json` completo
- Fallo del proceso: exit code fuera de `allowed_exits` → `failed` con código `nonzero_exit`
- Postcondición incumplida: artefacto faltante o con fecha equivocada → `postcondition_failed`
- Validación: petición inválida → `blocked` con código `validation_error`
- Si es stateful: promoción correcta, y `blocked` con `snapshot_exists` al reintentar el mismo día

**El e2e no debe depender del ETL legacy real ni de datos de producción.** Usá los dobles de
`tests/support/` y fixtures sintéticas.

### Test de adapter (si escribiste una clase)

En `tests/adapters/`. Cubrí cada rama de `validate()` y la construcción del comando.

---

## Paso 5 — Verificar antes del PR

```bash
pytest                                    # los 13+ e2e tienen que seguir en verde
python -m orchestrator.run --etl micliente.base.daily --fecha $(date +%Y%m%d) --base ./fixtures/base.csv
uvicorn platform_api.main:app --reload    # el ETL aparece en GET /api/catalog
```

Checklist:

- [ ] El catálogo carga sin errores (si el YAML está mal, la API no arranca)
- [ ] El ETL aparece en `GET /api/catalog` con sus inputs y outputs correctos
- [ ] Una corrida real genera artefactos y `run.json` completo
- [ ] Un fallo simulado deja el código de error correcto en `run.json`
- [ ] El lock se libera al terminar, incluso ante fallo
- [ ] Ningún dato real quedó commiteado: revisá `git status` buscando `.csv`, `.xlsx`, `.env`
- [ ] `README.md` del cliente escrito, con las respuestas del Paso 0

---

## Errores frecuentes

| Síntoma | Causa habitual |
|---|---|
| La API no arranca | El YAML tiene un campo desconocido, un typo, o un ETL `executable: true` sin metadata completa |
| `CatalogError: executable ETL requires ready registered adapter` | La clave `adapter` del YAML no coincide con la del `dict` de `_adapters()` |
| `postcondition_failed: missing` | El glob no matchea. Verificá subcarpeta y mayúsculas |
| `postcondition_failed: wrong-date` | El `date_format` declarado no es el que usa el legacy. Es el error más común |
| `postcondition_failed: ambiguous` | El glob matchea más de un archivo. Hacelo más específico |
| `postcondition_failed: unchanged` | El legacy no regeneró el archivo. Suele ser que falló un paso sin devolver error |
| El legacy no encuentra sus archivos | Está usando rutas derivadas de `__file__` o del `cwd`. Necesitás wrapper |
| `blocked: lock_exists` | Quedó un lock huérfano de una corrida interrumpida. Liberalo con `POST /api/runs/{run_id}/actions/free_lock` |
| `blocked: snapshot_exists` | Ya se corrió ese ETL ese día. Es correcto: el sistema no permite doble corrida |
| `blocked: recovery_required` | Una promoción de estado quedó a medias. **No lo fuerces.** Revisá `var/state/<etl_id>/<YYYYMM>/` |

---

## Qué nunca hacer

- Meter reglas de negocio del cliente en `orchestrator/` o en el adapter. Van en el legacy.
- Escribir fuera del sandbox de la corrida.
- Commitear datos reales: `.csv`, `.xlsx`, `.xls`, `.env`, outputs generados.
- Modificar `MaVoicePctAdapter` para acomodar un cliente nuevo: hoy está compartido por nueve ETLs
  de seis clientes.
- Hardcodear rutas absolutas.
- Usar `except Exception` genérico en el núcleo o en un adapter. La única frontera fail-fast
  permitida es la de los `*_job.py`.
