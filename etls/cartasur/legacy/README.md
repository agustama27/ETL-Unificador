# CartaSur ETL

Transforma la base cruda de CartaSur (`CabeceraconDatos.xlsx` o CSV delimitado por `;`) en el archivo ROMAN `CARTA_SUR_ROMAN_YYMMDD.csv` para Sofía/Retell y genera en paralelo el CSV telefónico `CARTA_SUR_E1KIA_YYMMDD.csv`. El proceso toma las columnas operativas de la base, normaliza datos de cliente, agrupa por CUIL, separa préstamos de seguros, calcula deuda/tramo de mora y exporta las variables dinámicas en el orden esperado por SOHO.

## Instalación

```bash
python -m pip install -e ".[dev]"
```

## Uso

```bash
cartasur-etl --input "CabeceraconDatos (1).xlsx" --output-dir out --run-date 2026-06-22
```

`--input` acepta `.xlsx` o `.csv` delimitado por `;`.

También se puede ejecutar como módulo:

```bash
python -m cartasur_etl.cli --input "CabeceraconDatos (1).xlsx" --output-dir out
```

Archivos generados:
- `CARTA_SUR_ROMAN_YYMMDD.csv`: variables en orden SOHO, UTF-8 sin BOM, LF, coma, montos con punto decimal.
- `CARTA_SUR_E1KIA_YYMMDD.csv`: teléfonos normalizados/deduplicados para E1KIA, encabezado `tel_fijo;tel_celular`, UTF-8 sin BOM, LF y separador `;`.
- `validation_report.csv` y `validation_report.json`: descartes, no-call y supuestos aplicados.

## Proceso actual

El pipeline ejecuta estas etapas:

1. **Ingesta de Excel/CSV**: lee `.xlsx` o `.csv` delimitado por `;`, valida que existan las columnas requeridas y limpia espacios/celdas vacías.
2. **Clasificación de filas**: cada fila se clasifica como `LOAN`, `INSURANCE` o `UNKNOWN` según tenga datos de préstamo o seguro.
3. **Agrupación por cliente**: consolida todas las filas del mismo `CUIL` en una sola salida.
4. **Transformación de importes y contadores**: suma saldos de préstamos, suma seguros por separado, calcula productos, cuotas a vencer y máximo de días de mora.
5. **Normalización**: genera `id_llamada`, limpia documentos/CUIL, normaliza nombre, teléfono, montos, tramo de mora y fecha límite de pago.
6. **Validación**: descarta clientes con errores bloqueantes y reporta advertencias/supuestos en los reportes.
7. **Exportación ROMAN + E1KIA**: escribe el CSV final ROMAN con encabezado y columnas en el orden configurado, y en paralelo el CSV telefónico E1KIA desde los registros válidos.

## Mapeo desde base cruda a variables ROMAN

El mapeo configurable está en `src/cartasur_etl/config/default_mapping.yaml`.

| Variable ROMAN | Origen / cálculo actual |
|---|---|
| `id_llamada` | `CUIL` solo dígitos + `_YYYYMMDD` de la fecha de ejecución. |
| `id_cuil` | `CUIL`, dejando solo dígitos. Debe tener 11 dígitos para ser válido. |
| `id_documento` | `NRO DE DOCUMENTO`, dejando solo dígitos. |
| `customer_name` | `NOMBRE APELLIDO`, normalizado a espacios simples y formato título. Si los dos primeros tokens son iguales, se elimina el duplicado inicial. |
| `tel_cliente` | `TELEFONO CLIENTE`, dejando solo dígitos. Elimina ceros iniciales; si no empieza con `54` o `549`, antepone `549`. |
| `monto_saldo_exigible_ars` | Suma de `SALDO EXIGIBLE` solo de filas clasificadas como préstamo (`LOAN`). |
| `monto_seguro_ars` | Suma de `IMPORTE A ABONAR POR SEGURO` solo de filas clasificadas como seguro (`INSURANCE`). No se incluye en el total de deuda. |
| `monto_total_ars` | Igual a `monto_saldo_exigible_ars`; representa deuda de préstamos sin seguro. |
| `cnt_dias_mora` | Máximo `DIAS DE MORA` entre las filas de préstamo del cliente. |
| `cnt_cuotas_a_vencer` | Suma de `CANTIDAD DE CUOTAS A VENCER` entre las filas de préstamo. |
| `cnt_productos` | Cantidad de productos de préstamo con `NRO DE PRODUCTO`. |
| `txt_seguro_descripcion` | Descripciones únicas de `SEGURO DESCRIPCION` en filas de seguro, separadas por `;`. |
| `txt_productos_detalle` | Lista de `NRO DE PRODUCTO` de préstamos, separados por `;`. |
| `tipo_tramo_mora` | `PRE_MORA`, `MORA_TEMPRANA`, `FUERA_DE_ALCANCE` o `SIN_MORA`, según días de mora. |
| `fecha_hoy` | Fecha de ejecución en formato `YYYY-MM-DD`. |
| `fecha_limite_sistema` | Fecha calculada según tramo de mora. Vacía si no hay mora; usa domingos y feriados nacionales de Argentina como días no hábiles. |
| `txt_productos` | Detalle adicional por producto `LOAN`, al final del CSV. Formato: `[Producto <NRO> Saldo:<monto> CuotasAVencer:<int|null> NroCuota:<int|null> ; ...]`. |

Ejemplo de `txt_productos`:

```text
[Producto 6590651 Saldo:224200.00 CuotasAVencer:5 NroCuota:8 ; Producto 6683756 Saldo:163000.00 CuotasAVencer:13 NroCuota:3]
```

Esta columna no modifica los totales existentes: `monto_total_ars` y `monto_saldo_exigible_ars` siguen calculándose igual, y el seguro sigue separado en `monto_seguro_ars` / `txt_seguro_descripcion`.

## Columnas requeridas de la base cruda

El Excel/CSV debe incluir estas columnas:

| Campo interno | Columna en Excel |
|---|---|
| `id_cuil` | `CUIL` |
| `customer_name` | `NOMBRE APELLIDO` |
| `id_documento` | `NRO DE DOCUMENTO` |
| `id_producto` | `NRO DE PRODUCTO` |
| `nro_cuota` | `NRO DE CUOTA` |
| `saldo_exigible` | `SALDO EXIGIBLE` |
| `dias_mora` | `DIAS DE MORA` |
| `cuotas_a_vencer` | `CANTIDAD DE CUOTAS A VENCER` |
| `seguro_descripcion` | `SEGURO DESCRIPCION` |
| `importe_seguro` | `IMPORTE A ABONAR POR SEGURO` |
| `tel_cliente` | `TELEFONO CLIENTE` |

## Configuración

El mapeo y los parámetros viven en `src/cartasur_etl/config/default_mapping.yaml`. Para sobrescribirlos:

```bash
cartasur-etl --input CabeceraconDatos.xlsx --output-dir out --config mi_mapping.yaml
```

## Reglas implementadas

- Una salida por cliente (`id_cuil`).
- Una fila es `LOAN` si tiene producto, cuota y saldo exigible; es `INSURANCE` si tiene descripción e importe de seguro. Si cumple ambas condiciones, se prioriza `LOAN`.
- `monto_total_ars` incluye solo préstamos; el seguro va en `monto_seguro_ars`.
- `txt_productos` incluye solo filas `LOAN`; filas `INSURANCE` nunca generan segmentos.
- Los segmentos de `txt_productos` se ordenan por saldo descendente y, ante empate, por número de producto ascendente.
- Si un producto no tiene `NRO DE CUOTA` o `CANTIDAD DE CUOTAS A VENCER`, el campo se escribe como `null` y se registra una advertencia en `validation_report`.
- Los montos se exportan con 2 decimales y punto decimal.
- Mora `1–10`: `PRE_MORA`, fecha límite día 10 del mes de ejecución; después ajusta al próximo día hábil si cae domingo o feriado nacional argentino.
- Mora `11–30`: `MORA_TEMPRANA`, fecha límite `fecha_hoy + 3` días aceptados, salteando domingos y feriados nacionales argentinos. Sábado cuenta como día hábil.
- Mora `>30`: queda fuera del CSV de llamadas y se reporta como `NO_CALL`.
- Teléfonos no normalizables se mantienen como registro válido con teléfono vacío y advertencia en el reporte.
- El CSV E1KIA se genera solo desde clientes válidos ya filtrados. Limpia caracteres no numéricos, descarta vacíos/placeholders, elimina duplicados y, si un mismo número aparece como fijo `54` y celular `549`, conserva solo la representación celular. Con la fuente actual, `tel_cliente` se exporta como `tel_celular`.

## Validaciones y descartes

Un cliente no entra al CSV ROMAN si tiene alguno de estos errores:

- `INVALID_CUIL`: el CUIL normalizado no tiene 11 dígitos.
- `MISSING_NAME`: falta nombre y apellido.
- `NO_POSITIVE_LOAN_BALANCE`: no tiene saldo positivo de préstamo o no tiene productos de préstamo.
- `MORA_OUT_OF_SCOPE`: la mora es mayor a 30 días; se reporta como `NO_CALL`.

Además, el reporte incluye advertencias por supuestos operativos configurados, por ejemplo normalización de teléfonos, deduplicación de nombres, feriados locales configurados y tratamiento de seguros.

## Riesgos pendientes de validar con CartaSur

- Regla exacta de deduplicación de nombres.
- Si todos los teléfonos son celulares argentinos con código de área.
- Si deben agregarse feriados locales o excepcionales en `date.exclude_holidays`; los feriados nacionales de Argentina ya se detectan con la librería `holidays`.
- Tratamiento operativo definitivo para mora mayor a 30 días.
