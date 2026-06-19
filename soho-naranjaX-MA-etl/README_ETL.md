# ETL Naranja X -> SOHO

Script standalone para transformar el archivo Excel de Naranja X al formato CSV esperado por SOHO.

Ahora el codigo esta modularizado dentro de `back-base/`:

- `back-base/etl_naranjax.py`: entrypoint CLI y orquestacion del pipeline
- `back-base/etl/constants.py`: nombres de hoja, columnas y mapeos
- `back-base/etl/io.py`: `load_input` y `save_output`
- `back-base/etl/cleaners.py`: normalizacion/limpieza de telefonos, montos, emails y helpers
- `back-base/etl/transformers.py`: `transform` y reglas de negocio
- `back-base/etl/validators.py`: validaciones de esquema y helpers de chequeo

Convencion operativa vigente:

- `back-base/archivo-recibido/` contiene archivos de entrada
- `back-base/base-generada/` contiene salidas generadas
- `back-base/` centraliza codigo y datos operativos del ETL base

## Dependencias

- Python 3.10+
- `pandas`
- `openpyxl`

Instalacion sugerida:

```bash
python -m pip install pandas openpyxl
```

## Uso

```bash
python back-base/etl_naranjax.py --input "back-base/archivo-recibido/Formato completo de archivo de entrada.xlsx" --output_dir "back-base/base-generada"
```

Si no se pasan argumentos, el CLI usa por defecto:

- input: `back-base/archivo-recibido/Formato completo de archivo de entrada.xlsx`
- output_dir: `back-base/base-generada/`

En Windows, para el proceso diario con defaults, podes ejecutar `ejecutar_dia.bat` con doble click (acepta overrides opcionales via argumentos).

## Verificacion de regresion estructural

Para validar contrato de salida y evidencia de equivalencia controlada post-move:

```bash
python -m unittest discover -s "back-base/tests" -p "test_*.py" -v
```

Este check ejecuta el ETL con el mismo input de referencia y valida:

- header CSV contra golden file (`back-base/tests/golden_output_header.txt`)
- esquema esperado en orden exacto
- comparacion de contrato contra baseline historico `back-base/base-generada/NARANJAX_CARTERA_20260417.csv` (si existe)

Pruebas de integracion Fase 2 (CLI + diarios de fixture):

```bash
python -m pytest back-base/tests/test_cli_phase2_integration.py -q
```

## Argumentos

- `--input`: ruta del Excel origen (hoja `Asignacion`)
- `--output_dir`: carpeta destino del CSV
- `--planes`: archivo diario PLANES (`.xlsx`, hoja `default_1`)
- `--pagos`: archivo diario PAGOS (`.csv` separado por `;`) opcional, solo compatibilidad (ignorado en calculo)

## Fase 2 - defaults conservadores documentados

Cuando hay ambiguedad entre fuentes mensual/diaria, se mantiene compatibilidad hacia atras con estas reglas:

- Si no se informa `--planes`, se conservan montos/cajon del archivo mensual.
- Si `--planes` viene informado pero falta `nroproducto` puntual, ese registro mantiene montos/cajon mensual y se loguea warning.
- Si hay `cajon = CAN` en PLANES, ese `nroproducto` se excluye de salida (filtro de negocio Fase 2).
- Precedencia de cajon: `PLANES.cajon` > `base mensual.cajon`.
- PAGOS no impacta deuda/saldo/cajon ni filtros de estado. Si se informa, se toma solo para compatibilidad operativa.
- `recupero` y `tipo_pago` no se recalculan desde PAGOS; se conservan vacios o el valor previo de estado persistido.
- Las columnas dinamicas de planes (`plan_N_*`) solo aparecen cuando se informa `--planes`; sin diarios se preserva header historico.
- D3 temporal (Fase 3): para salida ROMAN (`NARANJAX_MA_ROMAN_YYYYMMDD.csv`) se excluyen del CSV las columnas `recupero` y `tipo_pago`; esos campos siguen vigentes en estado interno para reglas/filtros.
- Contrato ROMAN: se incluye `id_dni` (desde `DNI`/`dni` de base cruda) ubicado inmediatamente despues de `tel_3`.

## Salida

- Archivo CSV: `NARANJAX_CARTERA_YYYYMMDD.csv`
- Separador: `;`
- Encoding: `utf-8` (sin BOM)
- Line endings: `\n` (LF)
- Sin indice
- La columna de identificacion del documento de salida es `id_nro_dni`

## Ejemplo completo

```bash
python back-base/etl_naranjax.py \
  --input "back-base/archivo-recibido/Formato completo de archivo de entrada.xlsx" \
  --output_dir "back-base/base-generada"
```
