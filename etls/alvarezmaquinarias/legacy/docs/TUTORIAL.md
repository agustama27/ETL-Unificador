# Tutorial: procesar las bases desde consola

Guía paso a paso para generar los dos CSV de cobranzas. No hace falta saber
Python: se copian archivos a una carpeta y se ejecutan dos comandos.

**Política de documentación:** Los ejemplos son genéricos. No documente datos
de clientes ni detalles operativos específicos.

## Qué hace el proceso

Toma los cuatro exports de Autologica y produce dos archivos:

| Archivo | Para quién | Contenido |
|---|---|---|
| `ALVAREZ_MAQUINARIAS_ROMAN_YYMMDD.csv` | Gestión de cobranzas | Una fila por cliente, con saldo, productos y días de mora |
| `ALVAREZ_MAQUINARIAS_E1KIA_YYMMDD.csv` | Plataforma de llamadas | Una sola columna, `TelefonoCliente` |

`YYMMDD` es la fecha de la corrida. Los dos archivos siempre se generan juntos:
si algo falla, no se escribe ninguno.

## Preparación (una sola vez)

```bash
python -m pip install -r requirements.txt
```

Verificá que quedó bien:

```bash
python -m pytest tests/ -q
```

Tiene que decir `162 passed`. Si falla algo, no proceses: avisá antes.

## Corrida diaria

### Paso 1 — crear la carpeta del día

```bash
python main.py --preparar
```

Crea `inputs/<hoy>/` y te dice qué dejar adentro:

```
Partición de entrada: ...\inputs\2026-08-21
Dejá ahí los cuatro exports de Autologica (el nombre no importa):
  - saldos de clientes      .csv o .xls
  - maquinarias             .xlsx
  - remitos de servicios    .xlsx  (con 'servicio' en el nombre)
  - remitos de repuestos    .pdf
Después: python main.py --run-date 2026-08-21
```

### Paso 2 — copiar los cuatro exports

Copiá los archivos a esa carpeta **tal como los manda Autologica**. No hace
falta renombrarlos: cada fuente se reconoce por su extensión.

La única condición es que el remito de servicios tenga la palabra `servicio`
en el nombre, porque comparte extensión `.xlsx` con maquinarias. Los nombres
que manda Autologica ya la traen (`Remitos - Servicios. 12-08.xlsx`).

### Paso 3 — procesar

```bash
python main.py
```

Salida esperada:

```
Fuentes de la corrida:
  saldos       saldos Agosto.csv
  maquinarias  maquinarias 12-08.xlsx
  repuestos    REMITOS - REPUESTOS (4).pdf
  servicios    Remitos - Servicios. 12-08.xlsx
Roman (gestion):    ...\outputs\2026-08-21\ALVAREZ_MAQUINARIAS_ROMAN_260821.csv
Approach (llamadas): ...\outputs\2026-08-21\ALVAREZ_MAQUINARIAS_E1KIA_260821.csv
ARS excluidos: maquinarias=0, remitos_repuestos=0, remitos_servicios=0, saldos_generales=0
```

**Leé siempre el bloque "Fuentes de la corrida"** y confirmá que cada archivo
entró donde corresponde. Es la única forma de detectar que copiaste un export
viejo por error.

## Procesar un día que no es hoy

```bash
python main.py --preparar --run-date 2026-08-21
python main.py --run-date 2026-08-21
```

## Volver a generar una corrida ya hecha

Por seguridad el proceso no pisa archivos existentes. Para reemplazarlos:

```bash
python main.py --run-date 2026-08-21 --overwrite
```

Ojo: los días de mora se cuentan **desde el día en que ejecutás**, no desde la
fecha de la carpeta. Si necesitás regenerar exactamente el archivo que ya
entregaste, fijá la fecha de cálculo a mano:

```bash
python main.py --run-date 2026-08-21 --overwrite --reference-date 2026-08-21
```

## Mensajes que vas a ver, y qué significan

Estos son **avisos normales**, no errores. La corrida sigue:

| Mensaje | Qué significa |
|---|---|
| `N telefono(s) completado(s) con la caracteristica de su localidad` | Venían sin código de área y se reconstruyeron con la característica de la localidad del cliente |
| `N telefono(s) siguen incompletos ... CP sin mapear: 5736(1)` | No se pudo reconstruir. Si lista códigos postales, faltan en la tabla — pasalo a desarrollo |
| `cliente duplicado resuelto por ...` | El mismo deudor llegó con el nombre escrito de dos formas y se unificó |
| `linea de PDF descartada por formato inválido` | Una línea del PDF no tenía la forma esperada |
| `línea final truncada sin bloque de cliente, descartada` | El export cortó a mitad de la última página, sin datos de cliente |

## Errores que detienen la corrida

Todos abortan **antes** de escribir: nunca vas a quedarte con un archivo a medias.

**No existe la carpeta del día**

```
No existe la partición de entrada inputs/2026-08-21/.
Crearla con: python main.py --preparar --run-date 2026-08-21
```

Corré `--preparar` primero.

**No puede decidir qué archivo es cuál**

```
Entradas inválidas: maquinarias: no se pudo identificar un único archivo por su
extensión; servicios: no se pudo identificar un único archivo por su extensión.
Archivos en la partición: A.xlsx, B.xlsx, REMITOS - REPUESTOS (4).pdf, saldos Agosto.csv
```

Hay dos archivos peleando por la misma fuente. Dejá uno solo de cada tipo, o
indicá cuál usar:

```bash
python main.py --maquinarias "A.xlsx" --servicios "B.xlsx"
```

**Ya existen las salidas de ese día**

Agregá `--overwrite` si querés reemplazarlas.

**El archivo de saldos no tiene el formato esperado**

Se rechaza antes de transformar nada. Pedile a Autologica el export correcto:
CSV separado por coma en codificación CP1252, o el `.xls`.

## Todas las opciones

| Opción | Para qué |
|---|---|
| `--preparar` | Crea `inputs/<run-date>/` y termina |
| `--run-date AAAA-MM-DD` | Carpeta de entrada y de salida (default: hoy) |
| `--reference-date AAAA-MM-DD` | Desde qué día se cuentan los días de mora (default: hoy) |
| `--overwrite` | Permite reemplazar las salidas de esa carpeta |
| `--saldos`, `--maquinarias`, `--repuestos`, `--servicios` | Fijan un archivo puntual en vez de descubrirlo |
| `--input-date` + `--output-date` | Leer de una carpeta y escribir en otra |

## Dos cosas que conviene saber

**`FlagPrioridad` siempre dice `False`.** Ninguno de los cuatro exports trae
prioridad de cliente, así que la columna no tiene dato. No es un error de la
corrida: está pendiente de definición.

**La cobertura de teléfonos depende del formato de Saldos.** El export `.xls`
trae teléfono para ~91 % de los clientes; el `.csv` "ficha por página", para
~44 %. Si ves pocos teléfonos en el E1KIA, revisá primero con qué formato vino
Saldos antes de sospechar del proceso.

## Si algo no cierra

Antes de tocar código, corré la suite:

```bash
python -m pytest tests/ -v
```

El detalle técnico de cada regla está en `docs/ASSUMPTIONS.md` y
`docs/SPEC.md`.
