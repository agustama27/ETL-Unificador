# archivos_salida_BANCOR_exe

Workflow GUI ROMAN-only para generar salida CRM Bancor sin Retell ni API key.

## Que hace

- Permite seleccionar un unico archivo ROMAN (`.csv`) desde la interfaz.
- Crea historial diario en `DD-MM-YYYY/entrada` y `DD-MM-YYYY/salida`.
- Copia el archivo elegido a `entrada`.
- Reutiliza normalizacion ROMAN (`back-resultados`) y mapeo/validacion/generacion CRM (`back-cargaMasiva`).
- Genera salida en `salida`:
  - `YYYY-MM-DD_EVOLTIS.xlsx`
  - `YYYY-MM-DD_EVOLTIS.csv`

## Ejecucion local

Desde esta carpeta:

```bash
python -m pip install -r requirements.txt
python main.py
```

## Build EXE (Windows)

```bat
build_exe.bat
```

Genera el ejecutable en `dist/Resultados_BANCOR.exe`.
