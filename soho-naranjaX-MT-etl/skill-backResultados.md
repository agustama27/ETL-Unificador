---
name: back-resultados-pct
description: Porta el modulo back-resultados (tipificaciones IA voz -> contrato PCT) de NARANJAX MORA AVANZADA a otro proyecto similar (NARANJA X MORA TEMPRANA). Implementa ingesta ROMAN + LOGCALL, transformacion a 7 columnas, output csv pipe cp1252 con prefijo configurable. Trigger: hay que generar el archivo PCT diario en un ETL hermano.
---

# Skill — Back Resultados (Tipificaciones IA Voz -> PCT)

Proyecto fuente: `soho-naranjaX-MA-etl` (NARANJA X MORA AVANZADA, commit `ae800fa`).
Proyecto destino: NARANJA X MORA TEMPRANA u otro hermano.

Objetivo: replicar **exactamente** el procesamiento `back-resultados/` produciendo un csv con el contrato PCT. Esta skill define contratos NO negociables — el archivo de salida tiene que pasar por sistemas downstream que validan layout estricto.

## 0) Contrato de salida (NO NEGOCIABLE)

| Item | Valor |
|---|---|
| Nombre archivo | `<PREFIX>_YYYYMMDD.csv` (default `NARANJAX_PCT_`) |
| Delimitador | `\|` (pipe) |
| Encoding | `cp1252` (ANSI Windows) |
| Line terminator | `\n` (LF) |
| Quoting | `csv.QUOTE_NONE` con `escapechar="\\"` |
| Header | si (1 fila) |
| Columnas (7, en orden) | `DNI`, `TIPIFICACION`, `NROPRODUCTO`, `FECHA_PROMESA`, `MONTO_PROMESA`, `CALL_REFID`, `OBSERVACIONES` |
| Formato fecha output | `YYYYMMDD` |
| `OBSERVACIONES` max chars | `1500`, recortando en ultimo espacio antes del corte |
| `OBSERVACIONES` sanit. | reemplazar `""`, `\|`, `\\` por espacio **antes** del cap |

Header exacto:
```
DNI|TIPIFICACION|NROPRODUCTO|FECHA_PROMESA|MONTO_PROMESA|CALL_REFID|OBSERVACIONES
```

Si tu proyecto destino usa otro prefix (ej. `NARANJAX_PCT_MT_`), cambialo en `constants.OUTPUT_FILENAME_PREFIX` y nada mas. **No toques el resto del contrato.**

## 1) Layout a portar

Copiar como bloque atomico:

```
back-resultados/
  back_resultados_etl/
    __init__.py
    constants.py        # mapeos + contrato de salida
    cleaners.py         # normalizacion + fechas + truncado
    validators.py       # columnas requeridas + dni
    io.py               # load_input / save_output + alias resolver
    logcall.py          # build_logcall_input (ROMAN + LOGCALL)
    transformers.py     # transform() core
  etl_tipificaciones_ia_voz_pct.py   # CLI standalone
  roman/              # input drop folder (default)
  base-generada/      # output folder default
  tests/
```

E integrar en el `core/` del proyecto destino:
```
core/
  modelos.py                  # agregar ConfigTipificaciones, ResultadoTipificaciones
  procesar_tipificaciones.py  # orquesta load -> transform -> save
  log_bridge.py               # bind_log_callback (capturar logs al callback UI)
```

## 2) Constantes exactas (`back_resultados_etl/constants.py`)

### 2.1 Columnas fuente

```python
REQUIRED_SOURCE_COLUMNS = ["call_id", "id_cliente", "tipificaciones", "observaciones", "call_refid"]
OPTIONAL_SOURCE_COLUMNS = ["fecha_compromiso_tc", "fecha_compromiso_nd", "monto_compromiso", "id_nro_producto"]
```

### 2.2 Alias por columna (multi-nombre tolerante)

`COLUMN_ALIASES` resuelve nombres equivalentes a una clave canonica. Mantener estos alias salvo que MORA TEMPRANA use otros nombres en ROMAN:

| Canonica | Alias aceptados |
|---|---|
| `call_id` | `Call ID`, `call_id`, `CallID`, `[Entrada] call_id` |
| `call_refid` | `call_refid`, `CALL_REFID`, `Call ID` |
| `id_cliente` | `[Entrada] id_dni`, `id_dni`, `[Entrada] id_cliente`, `id_cliente`, `[Entrada] user_number`, `user_number`, `[Entrada] msisdn`, `msisdn`, `[Entrada] customer_id`, `customer_id` |
| `tipificaciones` | `[Salida] Tipificaciones`, `[Salida] tipificaciones`, `[Salida] categoria`, `Tipificaciones` |
| `observaciones` | `[Salida] observaciones`, `[Salida] OBSERVACIONES`, `observaciones` |
| `fecha_compromiso_tc` | `[Salida] fecha_compromiso_tc`, `fecha_compromiso_tc` |
| `fecha_compromiso_nd` | `[Salida] fecha_compromiso_nd`, `fecha_compromiso_nd` |
| `monto_compromiso` | `[Salida] Monto_compromiso`, `[Salida] monto_compromiso`, `Monto_compromiso` |
| `id_nro_producto` | `[Entrada] id_producto`, `id_producto`, `id_nro_producto`, `NROPRODUCTO`, `nro_producto` |

Normalizacion para matching: `unicodedata` NFD + remove combining + `[^A-Za-z0-9]+ -> _` + upper. Es decir, `[Entrada] id_dni` y `id_dni` matchean.

### 2.3 Mapeo de tipificaciones a codigo PCT (`TIPIF_MAP`)

```python
TIPIF_MAP = {
    "LOGCALL": "26",
    "PROMESA_DE_PAGO": "12",
    "DIFICULTAD_DE_PAGO": "47",
    "SIN_VOLUNTAD_DE_PAGO": "17",
    "NO_RECONOCE_DEUDA": "15",
    "MANIFIESTA_PAGO": "37",
    "NOTIFICADO_TITULAR": "8",
    "NOTIFICADO_FAMILIAR": "8",
    "CONOCE_TITULAR": "8",
    "NO_RESPONDE": "7",
    "CONTESTADOR": "29",
    "FALLECIDO": "16",
    "NO_ES_TITULAR": "61",
    "MENSAJE": "28",
}
```

ATENCION: si MORA TEMPRANA usa otros codigos PCT, validar con producto/operaciones antes de cambiar. Las claves se matchean post-`normalize_upper_snake` (sin tildes, mayusculas, snake).

## 3) Reglas de cleaning (`cleaners.py`)

- `to_clean_str(v)`: si NaN -> `""`; si texto `#N/A` (case-insensitive) -> `""`; sino `str(v).strip()`.
- `to_input_str_preserve(v)`: como `str(v)` sin strip — usado **solo para `DNI`** para no perder ceros a la izquierda o formatos.
- `normalize_upper_snake(v)`: NFD + remove Mn + `[^A-Za-z0-9]+ -> _` + strip `_` + upper.
- `format_fecha_compromiso(v)`: parsea **estrictamente** `%d/%m/%y` y devuelve `%Y%m%d`. Cualquier otro formato -> `""`. **No** asumir `%d/%m/%Y` ni ISO.
- `resolve_fecha_promesa(tc, nd)`: prioridad TC > ND > `""`.
- `truncate_observaciones(text, max=1500)`:
  1. Reemplaza `""`, `\|`, `\\` por espacio.
  2. Si `len <= max` devuelve tal cual.
  3. Si excede: corta a `max`, busca `rfind(" ")` y corta ahi (sino devuelve el chunk).

## 4) Transformacion (`transformers.py`)

Por cada fila del source canonizado (indice fila empezando en 2 para mensajes humanos):

1. `key = normalize_result_key(row["tipificaciones"])`
2. `codigo = TIPIF_MAP.get(key)`. Si no esta -> omit con motivo `unmapped_tipificacion`, log warning, continue.
3. `dni_raw = to_input_str_preserve(row["id_cliente"])` y `dni_clean = to_clean_str(row["id_cliente"])`.
4. `validate_dni(dni_clean)` (presente despues de clean). Si no -> omit con motivo `missing_dni`, log warning, continue.
5. `fecha = resolve_fecha_promesa(row["fecha_compromiso_tc"], row["fecha_compromiso_nd"])`.
6. Emitir registro:

```python
{
    "DNI": dni_raw,                                                          # preserva original
    "TIPIFICACION": codigo,
    "NROPRODUCTO": to_clean_str(row.get("id_nro_producto", "")),
    "FECHA_PROMESA": format_fecha_compromiso(fecha),
    "MONTO_PROMESA": to_clean_str(row.get("monto_compromiso", "")),
    "CALL_REFID": to_clean_str(row.get("call_refid", row.get("call_id", ""))),
    "OBSERVACIONES": truncate_observaciones(to_clean_str(row.get("observaciones", ""))),
}
```

`output_df.attrs` debe incluir: `total_input_rows`, `total_output_rows`, `omitted_rows_total`, `warning_count`, `omitted_by_reason` (Counter as dict). Esto lo lee la UI para el panel de metricas.

## 5) Ingesta LOGCALL (`logcall.py`)

`build_logcall_input(logcall_path, cruce_path)` es lo que permite cargar un LOGCALL crudo (calls sin respuesta) y enriquecerlo con un archivo de cruce ROMAN para resolver `id_cliente` / `id_nro_producto`.

### 5.1 Reglas

- Detecta columna `CALLREFID` (alias: `CALL_REFID`, `callrefid`, `call_refid`). Si no esta -> raise.
- Detecta columna `PHONE` (alias: `phone`, `msisdn`, `user_number`). Opcional.
- Normaliza telefono: solo digitos; si arranca con `549` quita los 3; si arranca con `54` quita los 2. (Cobertura AR celular+fijo).
- Base sintetica:
  - `call_refid = LOGCALL[CALLREFID].strip()`
  - `phone_norm = _clean_phone(LOGCALL[PHONE])`
  - `tipificaciones = "LOGCALL"` (mapea a codigo `26`)
  - `observaciones = "Cliente no responde. Intento de contacto sin éxito."`
  - `id_cliente`, `id_nro_producto`, `monto_compromiso`, `fecha_compromiso_tc`, `fecha_compromiso_nd` vacios.
  - `call_id = call_refid` (fallback).
- Si `cruce_path` provisto:
  1. Match por `call_refid` (dedup en cruce).
  2. Para filas sin `id_cliente` resuelto y con `phone_norm`, match por `phone_norm` (dedup).
  3. Si despues de ambos matches `id_cliente` sigue vacio -> usar `phone_norm` como fallback en `id_cliente` (peor caso queda el telefono).

### 5.2 Modos de invocacion en el orquestador

`procesar_tipificaciones` distingue dos modos por nombre de archivo:

- Si `input_path.name.upper().startswith("LOGCALL_")` -> `build_logcall_input(input_path, cruce_path)` directo.
- Si NO, pero hay `config.cruce_path` -> carga ROMAN normal + `build_logcall_input(cruce_path, cruce_lookup or input_path)` y concatena ambos.
- Sin `cruce_path` y sin prefijo `LOGCALL_` -> solo `load_input(input_path)`.

## 6) IO (`io.py`)

### 6.1 `load_input(filepath)`

1. Detecta extension: `.csv`/`.txt` -> `_load_delimited`; `.xlsx`/`.xls` -> `pd.read_excel(dtype=str)`.
2. `_load_delimited` prueba separadores en orden: `","`, `";"`, `"\t"`, `None` (auto). Acepta el primero que devuelva >1 columna. Engine `python`, `dtype=str`, `keep_default_na=False`.
3. Canoniza columnas via `COLUMN_ALIASES` + normalizacion. Si una canonica REQUERIDA no aparece bajo ningun alias -> raise `ValueError("Missing required source columns: ...")`.
4. Si varias originales mapean a la misma canonica, hace `coalesce` por orden de aparicion (donde una es vacia, usa la siguiente).
5. Llama a `validate_required_columns`.

### 6.2 `save_output(df, output_dir)`

```python
os.makedirs(output_dir, exist_ok=True)
filename = f"{OUTPUT_FILENAME_PREFIX}{date.today():%Y%m%d}{OUTPUT_FILENAME_EXTENSION}"
df.reindex(columns=OUTPUT_COLUMNS).to_csv(
    Path(output_dir) / filename,
    sep="|", header=True, index=False,
    encoding="cp1252", lineterminator="\n",
    quoting=csv.QUOTE_NONE, escapechar="\\",
)
```

## 7) Modelos en `core/modelos.py`

```python
@dataclass
class ConfigTipificaciones:
    output_dir: Path
    cruce_origen: str = "none"             # "none" | "logcall"
    cruce_path: Path | None = None         # archivo LOGCALL para combinar
    cruce_lookup_path: Path | None = None  # archivo ROMAN de referencia para resolver dnis del LOGCALL

@dataclass
class ResultadoTipificaciones:
    status: str                              # "success" | "error"
    total_input_rows: int = 0
    total_output_rows: int = 0
    omitted_rows_total: int = 0
    omitted_by_reason: dict[str, int] = field(default_factory=dict)
    warning_count: int = 0
    output_path: Path | None = None
    output_contract: dict = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)
```

## 8) Orquestador `core/procesar_tipificaciones.py`

Firma publica:

```python
def procesar_tipificaciones(
    input_path: Path,
    config: ConfigTipificaciones,
    log_cb: Callable[[str], None] | None = None,
) -> ResultadoTipificaciones
```

Pasos:

1. `with bind_log_callback(log_cb):` — bridge para redirigir logs `logging` -> callback UI.
2. Resolver `source_df` segun el modo descrito en 5.2.
3. `output_df = transform(source_df, logger=LOGGER)`.
4. `output_path = save_output(output_df, str(config.output_dir))`.
5. Devolver `ResultadoTipificaciones(status="success", ...)` con todas las metricas + `output_contract`.
6. Cualquier excepcion -> `LOGGER.exception(...)` + retorno `status="error"` con `errores=[str(exc)]`. **No** relanzar (la UI espera resultado tipado siempre).

Tambien exponer `resolve_tipificaciones_input_path(input_path)`:

- Si `input_path` viene -> devolverlo.
- Si None -> buscar en carpeta default (`<root>/back-resultados/roman/` o equivalente en destino), pickea el mas reciente entre `*.csv`, `*.xlsx`, `*.xls`. Si no hay archivos -> `FileNotFoundError` con mensaje accionable.

## 9) Integracion con UI (si el destino tiene UI customtkinter)

Worker (`ui/worker.py`):

```python
class BackResultadosWorkerThread(threading.Thread):
    def __init__(self, selected_input, output_dir, queue, cruce_origen="none",
                 cruce_path=None, cruce_lookup_path=None): ...
    def run(self):
        try:
            resolved = resolve_tipificaciones_input_path(Path(self._selected_input) if self._selected_input else None)
            self._queue.put(("log", f"Input seleccionado: {resolved}"))
            result = procesar_tipificaciones(resolved, ConfigTipificaciones(
                output_dir=Path(self._output_dir),
                cruce_origen=self._cruce_origen,
                cruce_path=Path(self._cruce_path) if self._cruce_path else None,
                cruce_lookup_path=Path(self._cruce_lookup_path) if self._cruce_lookup_path else None,
            ), log_cb=lambda line: self._queue.put(("log", line)))
            self._queue.put(("done", result))
        except Exception as exc:
            self._queue.put(("error", str(exc)))
```

Panel en `principal.py` con 4 rows: Input (radio `roman` / `file`), Input LOGCALL (file), Cruce LOGCALL (file), Output dir. Boton `Procesar`, label de status, label de metricas, boton `Abrir carpeta de salida`. Persistir las elecciones en `config_store` con claves:

- `back_resultados_input_mode` (`roman` | `file`)
- `back_resultados_input_file`
- `back_resultados_cruce_mode` (`logcall`)
- `back_resultados_cruce_file`
- `back_resultados_cruce_lookup_file`
- `back_resultados_output_dir`

Mensajes de error friendly (mapeo crudo -> humano):

| Substring crudo (lower) | Mensaje UI |
|---|---|
| `no input file selected` o `no files found in default folder` | "No hay input disponible: selecciona un archivo o carga uno en back-resultados/roman/." |
| `failed to read input file` | "No se pudo leer el archivo input. Verifica formato, permisos y que no este bloqueado." |
| `missing required source columns` | "El archivo no contiene columnas requeridas para Back Resultados. Revisa el layout de origen." |
| `unsupported input extension` | "Formato de archivo no soportado. Usa .csv, .txt, .xlsx o .xls." |
| `no such file` o `cannot find` | "No se encontro el archivo indicado. Verifica la ruta del input." |

## 10) CLI standalone (`back-resultados/etl_tipificaciones_ia_voz_pct.py`)

```
python back-resultados/etl_tipificaciones_ia_voz_pct.py \
    --input back-resultados/roman/<archivo>.csv \
    --output_dir back-resultados/base-generada \
    --log_level INFO
```

- Si `--input` se omite -> resuelve el mas reciente de `roman/`.
- `exit 0` ok, `exit 1` en error (logueado con `LOGGER.exception`).

## 11) Tests minimos a portar

Carpeta `back-resultados/tests/` debe cubrir:

- `test_tipificaciones_mapping.py` — todas las claves de `TIPIF_MAP` mappean a codigo correcto (PURO + ECOSISTEMICO).
- Output contract: header exacto, 7 columnas, `cp1252`, LF, `|`, sin quotes.
- `OBSERVACIONES` truncado a 1500 con sanitizacion previa de `""`, `|`, `\`.
- Hard-fail si faltan columnas requeridas (`Missing required source columns: ...`).
- LOGCALL: build_logcall_input con cruce resuelve dnis por callref y luego por phone, fallback a phone como id_cliente.
- Fecha: `25/12/26` -> `20261225`; cualquier otro formato -> `""`.

Criterio PASS:
```
python -m pytest back-resultados/tests -q
```

## 12) Checklist de adaptacion a MORA TEMPRANA

1. [ ] Copiar `back-resultados/` completo al proyecto destino.
2. [ ] Copiar `core/modelos.py` (clases `ConfigTipificaciones`/`ResultadoTipificaciones`), `core/procesar_tipificaciones.py`, `core/log_bridge.py`.
3. [ ] Confirmar con producto: `TIPIF_MAP` y `OUTPUT_FILENAME_PREFIX` (¿`NARANJAX_PCT_MT_`?). Cambiar SOLO si te lo confirman.
4. [ ] Confirmar formato fecha de origen (`%d/%m/%y`) — si el origen MT manda `%d/%m/%Y`, ajustar **solo** en `format_fecha_compromiso` y agregar test.
5. [ ] Adaptar `COLUMN_ALIASES` si el ROMAN de MT tiene encabezados distintos. Agregar alias, **no** quitar los existentes (rompe retrocompat).
6. [ ] Integrar al spec de PyInstaller del destino: `hiddenimports += collect_submodules("back_resultados_etl")` y `pathex` incluye `back-resultados/`.
7. [ ] Wire en la UI del destino (worker + panel de `principal.py` segun seccion 9).
8. [ ] Correr `pytest back-resultados/tests -q` y validar smoke CLI seccion 10.
9. [ ] Smoke output: abrir el csv generado en VSCode/Notepad++ y verificar encoding `cp1252`, LF y 7 columnas.

## 13) Anti-patrones

- **No** cambiar el delimitador, encoding o quoting "para que sea mas legible". Downstream lo parsea estricto.
- **No** trimear `DNI` antes de escribirlo: se preserva con `to_input_str_preserve` para no perder formato.
- **No** mapear nuevas tipificaciones sin confirmar codigo PCT — un codigo mal cae al sistema de gestion como otra cosa.
- **No** levantar excepciones desde `procesar_tipificaciones` hacia la UI: siempre `ResultadoTipificaciones(status="error", errores=[...])`.
- **No** asumir que el ROMAN viene con `dtype` correcto: SIEMPRE `dtype=str` al leer (preserva ceros a la izquierda).
- **No** modificar el orden de columnas en `OUTPUT_COLUMNS`: el contrato es posicional ademas de nominal.

## 14) Referencias en el proyecto fuente

- `back-resultados/back_resultados_etl/constants.py` — verdad sobre contrato y mapeos.
- `back-resultados/back_resultados_etl/io.py` — load/save con contrato estricto.
- `back-resultados/back_resultados_etl/logcall.py` — enriquecimiento ROMAN + LOGCALL.
- `back-resultados/back_resultados_etl/transformers.py` — reglas de transformacion fila a fila.
- `core/procesar_tipificaciones.py` — orquestacion + manejo de errores tipado.
- `ui/screens/principal.py` `_build_back_resultados_section` — UI de referencia.
- `ui/worker.py` `BackResultadosWorkerThread` — worker de referencia.
