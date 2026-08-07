# Guía — Cómo agregar un cliente nuevo

Procedimiento para integrar un ETL de un cliente nuevo. Con la Fase 3 del ADR-001
completa, **agregar un cliente = agregar una carpeta bajo `etls/`**: el catálogo la
descubre solo y no se toca ningún archivo del núcleo.

Lo primero: leé `docs/ARQUITECTURA.md`, en particular las secciones 5 (contrato de
adapter) y 6 (puente con el legacy). Después copiá `etls/_template/` como punto de
partida.

---

## Paso 0 — Relevar el ETL legacy

Antes de escribir una línea, respondé esto por escrito. Va a ser el `README.md` del cliente.

| Pregunta | Por qué importa |
|---|---|
| ¿Cuál es el entrypoint y qué argumentos acepta? | Define si necesitás un `job.py` |
| ¿Qué archivos de entrada requiere? ¿Cuáles son opcionales? | Va a `inputs` del manifiesto |
| ¿Qué archivos genera? ¿Con qué patrón de nombre y qué formato de fecha? | Va a `outputs`. Ojo: hay ETLs que mezclan `YYYYMMDD` y `YYMMDD` en la misma corrida |
| ¿Mantiene estado entre corridas? | Define `stateful` en el adapter |
| ¿Escribe logs propios? ¿Dónde? | El servicio los recoge de `logs/` y los normaliza |
| ¿Qué exit codes devuelve? ¿Devuelve `0` aunque falle? | Va a `allowed_exits`. Si el legacy se traga errores, las postcondiciones son tu única defensa |
| ¿Usa rutas relativas internas o derivadas de `__file__`? | Define si podés pasarle rutas por CLI o necesitás wrapper |
| ¿Cuánto tarda una corrida típica? | Va a `timeout_seconds`, con margen |
| ¿Cuál es el deadline operativo de entrega? | Va al README del cliente y a `DEADLINES`/`DEADLINE_HINTS` |
| ¿Qué variables de entorno o credenciales necesita? | Va a `environment_allowlist` |

Si algo no se puede responder mirando el código, **preguntá antes de asumir**. Un supuesto
equivocado sobre el formato de fecha de un output se descubre recién en producción, el día
de la entrega.

---

## Paso 1 — Decidir el adapter

Tres caminos, en orden de preferencia.

### A. El legacy ya tiene CLI limpia → `SubprocessAdapter` genérico

Si acepta `--input` y escribe donde le decís, no escribas código. Declaralo en el
manifiesto con `adapter: etl_core.contracts:SubprocessAdapter`. Es el caso de la mayoría
de los clientes actuales.

### B. El legacy no tiene CLI usable → wrapper `job.py`

Escribí `etls/<cliente>/job.py`: una CLI propia que recibe `--input` y `--output_dir`,
importa las funciones del legacy, las ejecuta en cadena fail-fast y copia los productos a
`output/`. Mirá `etls/petersen/job.py` como referencia limpia.

**No copies el patrón de `etls/bancor/job.py`**, que reasigna el `__file__` de un módulo
importado. Funciona pero es frágil. Preferí, en este orden: pasar rutas por argumento →
pasar rutas por variable de entorno → como último recurso, monkeypatch documentado con un
comentario que explique por qué no había alternativa.

### C. Hay reglas de validación propias → adapter con clase

Sólo si el cliente tiene reglas específicas sobre qué combinación de entradas es válida, o
postcondiciones que el mecanismo genérico no cubre. Mirá `etls/petersen/adapter.py`:
declara extras opcionales y compone `SubprocessAdapter` para las postcondiciones.

**Regla dura:** el adapter valida forma, no negocio. Si estás escribiendo una regla de
quita, un filtro de módulos o un criterio de exclusión, eso va en el legacy, no acá.

---

## Paso 2 — Armar la carpeta del cliente

```
etls/<cliente>/
├── manifest.yaml      declaración del catálogo (copiá el de _template)
├── __init__.py        vacío; hace importable el paquete
├── adapter.py         sólo si elegiste el camino C
├── job.py             sólo si elegiste el camino B
├── legacy/            el proyecto ETL original, SIN modificar
├── tests/             e2e sintético + unit del adapter/job
└── README.md          las respuestas del Paso 0
```

El campo `adapter` del manifiesto es una ruta de importación `modulo:Clase`
(`etls.<cliente>.adapter:MiAdapter` o `etl_core.contracts:SubprocessAdapter`). El catálogo
la importa, valida que satisfaga el Protocol `ETLAdapter` y recién ahí acepta el ETL como
ejecutable. Los campos y sus reglas de validación están en `docs/ARQUITECTURA.md` §4.

### Convenciones del manifiesto

- **`id`:** `<cliente>.<canal o proceso>.<variante>`, minúsculas, separado por puntos. El
  prefijo agrupa por cliente en la UI (`platform_api/catalog_meta.py::CLIENTS`).
- **`glob`:** relativo a `output/`, sin `..` ni rutas absolutas. Puede incluir subcarpeta.
- **`date_format`:** sólo `YYYYMMDD`, `YYMMDD` o `DDMMYYYY`; verificá cada salida por
  separado.
- **`command`:** relativo al `working_dir` (que suele ser `etls/<cliente>/legacy`); un
  `job.py` en la raíz del paquete se invoca como `[python, ../job.py]`.
- **ETLs todavía no implementados:** `executable: false` + motivo legible en
  `INERT_REASONS` (`platform_api/catalog_meta.py`) — único archivo compartido que se toca,
  junto con `CLIENTS` para el nombre legible.

---

## Paso 3 — Escribir los tests

### Test e2e (obligatorio)

Copiá `etls/petersen/tests/test_petersen_gestiones.py` como plantilla. Tiene que cubrir:

- Corrida feliz: `succeeded`, artefactos con el rol correcto, `run.json` completo
- Fallo del proceso: exit fuera de `allowed_exits` → `failed` / `nonzero_exit`
- Postcondición incumplida: artefacto faltante o con fecha equivocada → `postcondition_failed`
- Validación: petición inválida → `blocked` / `validation_error`
- Si es stateful: promoción correcta y `blocked` / `snapshot_exists` al reintentar el día

**El e2e no debe depender del ETL legacy real ni de datos de producción.** Usá los dobles
de `tests/support/` y fixtures sintéticas.

### Test de adapter/job (si escribiste código)

En `etls/<cliente>/tests/`. Cubrí cada rama de `validate()` y la construcción del comando.

---

## Paso 4 — Verificar antes del PR

```bash
pytest                                    # los 13+ e2e tienen que seguir en verde
python -m orchestrator.run --etl micliente.base.daily --fecha $(date +%Y%m%d) --base ./fixtures/base.csv
uvicorn platform_api.main:app --reload    # el ETL aparece en GET /api/catalog
```

Checklist:

- [ ] El catálogo carga sin errores (si el manifiesto está mal, la API no arranca)
- [ ] El ETL aparece en `GET /api/catalog` con inputs, outputs y `params` correctos
- [ ] Una corrida real genera artefactos y `run.json` completo
- [ ] Un fallo simulado deja el código de error correcto en `run.json`
- [ ] El lock se libera al terminar, incluso ante fallo
- [ ] Ningún dato real quedó commiteado: revisá `git status` buscando `.csv`, `.xlsx`, `.env`
- [ ] `README.md` del cliente escrito, con las respuestas del Paso 0

---

## Errores frecuentes

| Síntoma | Causa habitual |
|---|---|
| La API no arranca | El manifiesto tiene un campo desconocido, un typo, o un ETL `executable: true` sin metadata completa |
| `CatalogError: executable ETL requires ready registered adapter` | La ruta `modulo:Clase` no importa, la clase no existe, o no satisface el Protocol `ETLAdapter` |
| `cannot resolve adapter reference` | Falta el `__init__.py` del paquete, o el módulo tiene un error de import |
| El upload devuelve "El ETL no declara la entrada" | El rol del form no coincide con un `role` de `inputs` en el manifiesto |
| `postcondition_failed` con el legacy en verde | El `glob` o el `date_format` del output no coinciden con lo que el legacy realmente genera |
