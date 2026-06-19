# GeneracionBase EXE

Aplicacion de escritorio para seleccionar una base (CSV/Excel), conservar la base recibida y generar la salida con la misma logica de `back-base`.

## Flujo funcional

1. Abrir la app.
2. Hacer click en `Seleccionar base a procesar`.
3. Elegir archivo `.csv`, `.xlsx` o `.xls`.
4. La app guarda:
   - `salidas/DD-MM-YYYY/Base Recibida/<archivo_original>.<ext>` (copia exacta del input seleccionado)
   - `salidas/DD-MM-YYYY/Base Generada/base_epec_DDMMYYYY.csv`
   - `salidas/DD-MM-YYYY/Base Generada/telefonos_epec_DDMMYYYY.csv`

Si ya existe un archivo del mismo dia, se agrega sufijo con timestamp para no pisarlo:
- `base_epec_DDMMYYYY_HH-MM-SS-ffffff.csv`
- `telefonos_epec_DDMMYYYY_HH-MM-SS-ffffff.csv`

La salida replica el proceso de `back-base`: normalizacion de fecha/motivo, saneamiento de texto, normalizacion y validacion de telefonos, deduplicacion por PK `TELEFONO;TELEFONO_CELULAR`, `CONNECTION_RESULT` y generacion del archivo de telefonos.

## Requisitos

- Python 3.10+
- pip

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar en modo UI

```bash
python main.py
```

## Ejecutar en modo CLI (validacion rapida)

```bash
python main.py --process-file "C:\ruta\archivo.csv"
```

## Build de ejecutable (Windows)

```bash
pyinstaller --noconsole --onefile --name generacion-base main.py
```

El ejecutable queda en `dist\generacion-base.exe`.

Al correr el EXE, la carpeta `salidas` se crea siempre junto al ejecutable (por ejemplo `dist\salidas\DD-MM-YYYY\...`).
