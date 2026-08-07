# Regresion back-base vs generacionBase-exe

Script para validar que ambos flujos generan outputs equivalentes de negocio para el mismo input canonico.

## Ejecutar (default)

Desde la raiz del workspace:

```bash
python scripts/regression_backbase_vs_generacionbase.py
```

Defaults:
- Input: `back-base/base-recibida/input_1_luz_16_04_26 (2).xlsx`
- Ejecuta ambos procesamientos en una carpeta temporal aislada.
- Compara `base_epec_*.csv` y `telefonos_epec_*.csv` con normalizacion deterministica.

## Parametros utiles

- `--input "<ruta>"`: usa otro input canonico.
- `--keep-temp`: conserva la carpeta temporal para inspeccion.
- `--back-base-base-csv` y `--back-base-phones-csv`: reutiliza outputs existentes de back-base.
- `--gen-base-csv` y `--gen-phones-csv`: reutiliza outputs existentes de generacionBase-exe.

Ejemplo en modo reutilizacion completa:

```bash
python scripts/regression_backbase_vs_generacionbase.py \
  --back-base-base-csv "back-base/base-generada/base_epec_17042026.csv" \
  --back-base-phones-csv "back-base/base-generada/telefonos_epec_17042026.csv" \
  --gen-base-csv "generacionBase-exe/dist/salidas/17-04-2026/Base Generada/base_epec_17042026.csv" \
  --gen-phones-csv "generacionBase-exe/dist/salidas/17-04-2026/Base Generada/telefonos_epec_17042026.csv"
```

## Criterio de salida

- Exit `0`: equivalencia OK.
- Exit `1`: mismatch en columnas, cantidad de filas o contenido.
