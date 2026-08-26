# ETL de cobranzas

Procesa cuatro archivos de entrada y genera dos exportaciones para una corrida
local. Esta guía describe el contrato operativo sin incluir datos, identidades
ni detalles de una operación real.

**Política de documentación:** Los ejemplos son genéricos. No documente datos
de clientes ni detalles operativos específicos.

## Corrida diaria

Dos pasos, sin renombrar archivos:

```bash
python main.py --preparar     # crea inputs/<hoy>/ y dice qué dejar adentro
# copiá ahí los cuatro exports tal como los manda Autologica
python main.py                # procesa esa partición
```

Sin `--run-date`, ambos comandos usan la fecha de hoy. Los cuatro exports se
identifican por su extensión, así que el nombre del archivo no importa:
`.csv`/`.xls` es saldos, `.pdf` es repuestos, y de los dos `.xlsx` el que
tenga `servicio` en el nombre es remitos de servicios y el otro maquinarias.
Antes de procesar, la corrida imprime qué archivo entró como qué fuente.

Si dos archivos compiten por la misma fuente, la corrida aborta y lista lo que
encontró: preferimos un fallo ruidoso a elegir una fuente al azar. En ese caso
fijá el archivo a mano con `--saldos`, `--maquinarias`, `--repuestos` o
`--servicios`, que siguen teniendo precedencia sobre el descubrimiento.

## Ejecución

Instalá las dependencias y generá datos sintéticos si necesitás probar la
corrida localmente:

```bash
python -m pip install -r requirements.txt
python scripts/generate_sample_data.py --run-date 2026-08-04
python main.py --run-date 2026-08-04
```

`--run-date` selecciona la partición de almacenamiento y `--reference-date`
define, de forma independiente, la fecha de cálculo. Usá `--overwrite` solo
para reemplazar las salidas fijas de la partición seleccionada.

El ETL procesa únicamente saldos explícitamente clasificados como USD. Las
filas ARS se excluyen en la extracción, antes de identidad, teléfonos, totales
y exportaciones. Al finalizar informa solo conteos agregados por fuente.
Durante esta versión, `--tipo-cambio` es opcional: un valor finito y positivo
se acepta con advertencia de obsolescencia, pero no afecta el resultado.

## Entradas y salidas

Colocá los cuatro archivos requeridos exclusivamente en
`inputs/<run-date>/`. Se aceptan los nombres predeterminados, el nombre con el
que Autologica los exportó (identificados por extensión), o un basename con la
extensión esperada, por ejemplo:

```bash
python main.py --run-date 2026-08-04 --maquinarias cierre.xlsx
```

### Saldos CSV

`--saldos` conserva `saldos.xls` como valor predeterminado. Para usar CSV,
pasá un basename como `--saldos saldos.csv`. Se admiten dos layouts CP1252
separados por coma, detectados por la firma de la primera línea: el reporte
seccionado con encabezados completos, y el export "ficha por página" de
Saldos de clientes (bloques `Cliente:` con nombre e ID, seguidos de su fila
de saldos; solo se toma el Saldo DOLARES). Si ese export viene cortado a
mitad del header de la última página, la cola se descarta con un warning
únicamente cuando no contiene un bloque de cliente; con datos de cliente en
la cola, la corrida aborta. Cualquier otro CSV inválido aborta antes de
transformar o escribir, sin salidas parciales.

Los teléfonos del export por página suelen venir sin característica; el
adapter los completa con la de la localidad del cliente (tabla en
`src/etl/codigos_area.py`) y lo informa como conteo agregado. Ver
`docs/ASSUMPTIONS.md`.

Las rutas arbitrarias de entrada y el argumento legado `--output` se rechazan.
Las exportaciones se escriben solo en `outputs/<run-date>/` con los nombres
fijos `ALVAREZ_MAQUINARIAS_ROMAN_YYMMDD.csv` (gestión) y
`ALVAREZ_MAQUINARIAS_E1KIA_YYMMDD.csv` (llamadas), donde `YYMMDD` es la fecha
de `--run-date`. Con `--run-date 2026-08-04` salen como
`ALVAREZ_MAQUINARIAS_ROMAN_260804.csv` y `ALVAREZ_MAQUINARIAS_E1KIA_260804.csv`.
`inputs/` y `outputs/` están ignorados por Git: no agregues su contenido al
repositorio.

### Formato de intercambio

Los dos archivos son CSV con separador `;`, codificación UTF-8 sin BOM y
terminador de línea CRLF. Sin BOM a propósito: el consumidor pidió ASCII/UTF-8
y el BOM no es ninguno de los dos.

Ojo con `Productos` y `ProductosRemitos`: contienen `;` internamente, así que
el writer las entrecomilla. Se leen bien con cualquier parser CSV real
(`pd.read_csv(path, sep=";", encoding="utf-8")`), pero un `split(';')` a mano
te parte esas filas en columnas de más.

### Relación entre los dos archivos

El ROMAN es la gestión completa: una fila por cliente, con o sin teléfono. El
E1KIA es el marcador, y trae **una sola columna**, `TelefonoCliente`.

Los dos cubren exactamente el mismo universo de teléfonos, y el pipeline lo
verifica antes de escribir: si el conjunto no coincide o el E1KIA trae un
repetido, la corrida aborta sin dejar archivos parciales.

La correspondencia es entre **conjuntos de teléfonos**, no entre filas. El
ROMAN puede tener dos clientes distintos que comparten línea (una persona y su
razón social, por ejemplo); el E1KIA lista ese número una sola vez, porque la
plataforma marca números, no clientes. Por eso el E1KIA suele tener menos
filas que clientes llamables tiene el ROMAN.

### Columnas de la salida

Una fila por cliente. `SaldoExigibleUSD` es la suma de todas sus deudas y
`Productos` el desglose como array `producto:monto` separado por `;`
(entrecomillado en el CSV, porque `;` es también el separador de campos).

Dos columnas merecen aclaración:

- **`Productos`** — las deudas de Remitos (Servicios, Repuestos) van
  consolidadas en una sola entrada por categoría. Esas fuentes no traen el
  concepto individual, así que repetir `Servicios:435.60;Servicios:176.95;…`
  produciría entradas indistinguibles entre sí sin agregar información. Las
  demás fuentes conservan una entrada por deuda: ahí el producto sí es dato
  real (la unidad de maquinaria, la cuenta corriente), y dos unidades del
  mismo modelo son dos deudas distintas que no deben fusionarse.
  `CantidadProductos` cuenta las entradas del array, no las filas de origen.
- **`ProductosRemitos`** — repite solo las entradas originadas en Remitos, en
  el mismo formato. Queda vacío cuando el cliente no tiene deuda de Remitos,
  así que sirve directo como filtro de segmentación.

## Pruebas

```bash
python -m pytest tests/ -v
```

La suite crea fixtures sintéticos y no requiere archivos operativos.
