# UAT - NaranjaX MT ETL

## Criterios PASS

- `dist-<rama>-<commit>\naranjax_mt_etl.exe` abre por doble clic sin consola.
- Cold start: cerrar, reiniciar sesion y abrir nuevamente.
- Si falta `estado_YYMM.csv`, se informa y no habilita procesar hasta corregir.
- CLI valido retorna `exit code 0` y respeta `--salida` y `--estado`.
- CLI invalido retorna `exit code != 0`.
- `build-info.txt` existe con `branch=`, `commit=`, `timestamp=`, `dirty=`.

## Comandos utiles

```bat
set BUILD_DRY_RUN=1 && packaging\build.bat
packaging\build.bat
```

## Metadatos e icono

- Icono por defecto: `packaging/assets/app.ico` (si existe se inyecta automaticamente).
- Override de icono: `set APP_ICON=C:\ruta\mi_icono.ico`
- Version de archivo/producto: `set APP_VERSION=1.2.3.0`
- Metadatos opcionales:
  - `set APP_PRODUCT_NAME=...`
  - `set APP_COMPANY_NAME=...`
  - `set APP_FILE_DESCRIPTION=...`
  - `set APP_COPYRIGHT=...`
