# Luz EXE

Aplicacion de escritorio para ejecutar el flujo `luz` usando la misma logica de consolidacion de `back-resultados` (Roman + Logcall), sin retell, sin tipif y sin update-tipif.

## Flujo funcional

1. Abrir la app (`python main.py` o `luz.exe`).
2. Seleccionar uno o varios CSV de Roman.
3. Seleccionar uno o varios CSV de Logcall.
4. Hacer click en `Procesar`.

La app crea una corrida con trazabilidad completa junto al ejecutable:

- `salidas/DD-MM-YYYY/corrida_HH-MM-SS-ffffff/entradas/roman/*.csv`
- `salidas/DD-MM-YYYY/corrida_HH-MM-SS-ffffff/entradas/logcall/*.csv`
- `salidas/DD-MM-YYYY/corrida_HH-MM-SS-ffffff/resultados/output_luz_DD_MM_YY.xlsx`
- `salidas/DD-MM-YYYY/corrida_HH-MM-SS-ffffff/logs/luz_YYYYMMDD_HHMMSS.log`

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

## Ejecutar en modo CLI (smoke test)

```bash
python main.py --roman-files "C:\ruta\roman_1.csv" "C:\ruta\roman_2.csv" --logcall-files "C:\ruta\logcall_1.csv"
```

## Smoke test de arranque UI

```bash
python main.py --smoke-ui
```

## Build de ejecutable (PyInstaller)

Desde esta carpeta (`luz-exe`):

```bash
pyinstaller luz.spec
```

Salida esperada:

- `dist\luz.exe`

Notas:

- El output persistente siempre se genera junto al ejecutable (`dist\salidas\...`) o junto al script (`luz-exe\salidas\...`).
- No se usa `_MEI` para outputs.
