# Especificación operativa del ETL

Esta especificación define el comportamiento general del ETL sin registrar
datos, identidades ni observaciones de una operación real.

**Política de documentación:** Los ejemplos son genéricos. No documente datos
de clientes ni detalles operativos específicos.

## Contrato de almacenamiento

- La corrida lee únicamente desde `inputs/<run-date>/`.
- La corrida escribe únicamente en `outputs/<run-date>/`.
- `--run-date` usa una fecha ISO `YYYY-MM-DD`; si falta, se usa la fecha local.
- `--reference-date` es independiente de `--run-date`.
- Cada fuente acepta solo un basename con la extensión esperada. No se aceptan
  rutas absolutas, separadores ni nombres que escapen de la partición.
- `--output` es un argumento legado y se rechaza con una guía de migración.
- `--overwrite` permite reemplazar exclusivamente las salidas fijas de la
  partición seleccionada.

## Resolución de la fuente de cada rol

El nombre de archivo de cada fuente se resuelve en tres niveles, en este orden:

1. El basename que indicó el operador (`--saldos`, `--maquinarias`,
   `--repuestos`, `--servicios`). Manda siempre; si no está, la corrida aborta.
2. El nombre canónico (`saldos.xls`, `maquinarias.xlsx`, `repuestos.pdf`,
   `servicios.xlsx`), si está presente en la partición.
3. Descubrimiento por extensión dentro de la partición: `.csv`/`.xls` es
   saldos y `.pdf` es repuestos; de los dos `.xlsx`, el que contiene
   `servicio` en el nombre es servicios y el restante es maquinarias.

El descubrimiento solo propone un nombre: las validaciones de la sección
siguiente se aplican igual sobre el archivo elegido. Si una regla no resuelve
a exactamente un archivo, esa fuente queda sin asignar y la corrida aborta
nombrando los archivos presentes en la partición. `--preparar` crea
`inputs/<run-date>/` y termina, sin procesar.

## Seguridad de entradas

Antes de extraer datos, el sistema valida que cada archivo sea regular,
legible y permanezca dentro de `inputs/<run-date>/` tras resolver enlaces. Si
hay más de una entrada inválida, informa sus roles sin mostrar contenido.

### Saldos CSV

`--saldos` mantiene `saldos.xls` por defecto y también acepta el basename
`saldos.csv`. El CSV soportado es exclusivamente CP1252 separado por coma, en
dos layouts detectados por la firma de la primera línea: el reporte seccionado
completo de saldos, y el export "ficha por página" de Saldos de clientes
(bloque `Cliente:` → `NOMBRE (ID)` y `Teléfono:`, seguido de la fila de
saldos, de la que se toma solo el Saldo DOLARES). No hay autodetección de
encoding ni dialecto. Una cola final truncada del export por página se
descarta con warning solo si no contiene un bloque de cliente; si lo
contiene, la corrida aborta. Cualquier otra validación CSV fallida detiene la
corrida antes de las transformaciones y deja sin salidas parciales.

## Exportaciones

El pipeline verifica ambas exportaciones fijas antes de crear la salida o
invocar cargadores. Sin `--overwrite`, una colisión detiene la corrida sin
generar resultados parciales. Los únicos nombres de salida son
`ALVAREZ_MAQUINARIAS_ROMAN_YYMMDD.csv` y `ALVAREZ_MAQUINARIAS_E1KIA_YYMMDD.csv`,
donde `YYMMDD` es la fecha de `--run-date` (la partición), no la de cálculo.

Ambos archivos usan el mismo formato de intercambio, pedido por los dos
consumidores: CSV con separador `;`, codificación UTF-8 sin BOM y terminador
de línea CRLF. Las columnas `Productos` y `ProductosRemitos` contienen `;`
internamente, así que el writer las entrecomilla: se leen con cualquier parser
CSV real, pero no con un `split(';')` a mano.

El ROMAN lleva todas las columnas de salida; el E1KIA lleva solo
`TelefonoCliente`. `verify_phone_parity` corre antes de escribir y aborta la
corrida si el E1KIA trae teléfonos repetidos o si su conjunto de teléfonos no
es idéntico al del ROMAN. La paridad es entre conjuntos, no entre filas: dos
clientes del ROMAN pueden compartir línea y el E1KIA lista ese número una vez.

## Pruebas

Las pruebas usan fixtures sintéticos creados en directorios temporales. La
ejecución requerida es:

```bash
python -m pytest tests/ -v
```
