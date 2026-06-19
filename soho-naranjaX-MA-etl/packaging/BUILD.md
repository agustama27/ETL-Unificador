# BUILD / UAT - Fase 4 (modo cierre)

Este documento define la validacion limpia en Windows sin Python instalado en maquina destino.

## Convencion de build por rama

- `packaging\\build.bat` detecta rama + commit corto y genera el ejecutable en `dist-<rama-normalizada>-<commit>\\naranjax_etl.exe`.
- Normalizacion Windows: reemplaza `/` y `\\` por `-` para asegurar una carpeta valida en ramas tipo `feature/x`.
- Ejemplo: rama `feature/archivoPagos`, commit `a1b2c3d` -> carpeta `dist-feature-archivoPagos-a1b2c3d`.
- Override manual soportado con variable de entorno `DIST_DIR`.
- Build limpio obligatorio por defecto: si hay cambios sin commit en el working tree, el script aborta.
- Override explicito para casos excepcionales: `ALLOW_DIRTY_BUILD=1`.
- Metadata obligatoria en cada build: `build-info.txt` con rama, commit, timestamp y dirty true/false.

Comandos:

```bat
packaging\build.bat
```

```bat
set DIST_DIR=C:\tmp\dist-manual && packaging\build.bat
```

```bat
set ALLOW_DIRTY_BUILD=1 && packaging\build.bat
```

Dry-run de resolucion de ruta (sin build):

```bat
set BUILD_DRY_RUN=1 && packaging\build.bat
```

## 1) Prerequisitos

- SO: Windows 10/11 x64.
- Artefacto disponible: `dist-<rama-normalizada>-<commit>\naranjax_etl.exe`.
- Metadata de build: `dist-<rama-normalizada>-<commit>\build-info.txt`.
- Permisos de lectura sobre archivos de entrada (base mensual, PLANES mensual, PAGOS diario).
- Permisos de escritura en carpeta temporal local (para no tocar salida/estado productivo).
- No requiere Python en maquina destino.

## 2) Validacion UI (doble clic + cold start)

1. Cerrar cualquier instancia previa de `naranjax_etl.exe`.
2. Hacer doble clic en `dist-<rama-normalizada>-<commit>\naranjax_etl.exe`.
3. Verificar que la UI abre sin error de runtime (sin popup de dependencia faltante).
4. Cerrar la UI.
5. Repetir apertura (cold start) luego de reiniciar sesion o reiniciar equipo.
6. Confirmar que vuelve a iniciar correctamente en primer intento.

Si al seleccionar la base mensual aparece aviso de estado faltante (`estado_YYMM.csv`):

7. Usar el boton `Generar estado inicial`.
8. Verificar en la carpeta de estado configurada que se crea `estado_YYMM.csv`.
9. Confirmar que el boton `Procesar` queda habilitado luego de generar estado y seleccionar todos los insumos.

Resultado esperado:

- PASS: la UI abre y cierra normalmente en ambas ejecuciones.
- FAIL: no inicia, crashea, o muestra error de dependencia/permiso al arrancar.

## 3) Validacion CLI exitosa

Usar rutas reales de entrada y rutas temporales para salida/estado.

Comando (ejemplo):

```powershell
dist-<rama-normalizada>\naranjax_etl.exe --cli --base "C:\RUTA\BASE\base_mensual.xlsx" --planes "C:\RUTA\BASE\planes_mensual.xlsx" --pagos "C:\RUTA\DIARIOS\pagos.csv" --estado "C:\TEMP\nx_uat\estado" --salida "C:\TEMP\nx_uat\salida" --fecha 20260428
```

Chequeos:

1. El proceso finaliza con `exit code = 0`.
2. Se genera salida en carpeta temporal (`--salida`).
3. Se genera/actualiza estado en carpeta temporal (`--estado`).
4. No se modifican carpetas productivas.

## 4) Validacion de caso invalido

Objetivo: comprobar manejo de error y codigo de salida sin tocar datos productivos.

Comando sugerido (flag invalida controlada):

```powershell
dist-<rama-normalizada>\naranjax_etl.exe --cli --arg-no-existe --base "C:\RUTA\BASE\base_mensual.xlsx" --planes "C:\RUTA\BASE\planes_mensual.xlsx" --pagos "C:\RUTA\DIARIOS\pagos.csv" --estado "C:\TEMP\nx_uat\estado" --salida "C:\TEMP\nx_uat\salida" --fecha 20260428
```

Resultado esperado:

- PASS: finaliza con `exit code != 0` y muestra error de argumentos/validacion.
- FAIL: finaliza con `exit code = 0` o no reporta error de entrada invalida.

## 5) Criterios de aceptacion (pass/fail)

Liberacion Fase 4 en modo cierre = PASS solo si se cumplen todos:

- `dist-<rama-normalizada>-<commit>\naranjax_etl.exe` existe y abre UI por doble clic.
- `dist-<rama-normalizada>-<commit>\build-info.txt` existe y refleja branch/commit esperados.
- Cold start UI exitoso (segunda ejecucion limpia).
- CLI valido retorna `0` y escribe solo en rutas temporales de UAT.
- CLI invalido retorna no-cero y deja evidencia de validacion.
- No se requiere Python instalado en destino.

Si cualquier punto falla, el estado global es FAIL.

## 6) Plantilla breve de evidencia

Copiar y completar:

```text
Fecha/Hora:
Tester:
Maquina:
Version artefacto: dist-<rama-normalizada>\naranjax_etl.exe
Build info: dist-<rama-normalizada>-<commit>\build-info.txt

UI doble clic: PASS/FAIL
UI cold start: PASS/FAIL
CLI valido (exit=0): PASS/FAIL
CLI invalido (exit!=0): PASS/FAIL

Rutas usadas:
- base:
- planes mensual:
- pagos:
- estado(tmp):
- salida(tmp):

Observaciones:
Evidencia adjunta (capturas/logs):
Resultado final UAT: PASS/FAIL
```

## 7) Smoke rapido con script (PowerShell)

Para una corrida rapida automatizada, usar:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\uat_quick.ps1 -ExePath "dist-<rama-normalizada>-<commit>\naranjax_etl.exe" -BasePath "C:\RUTA\BASE\base_mensual.xlsx" -PlanesPath "C:\RUTA\BASE\planes_mensual.xlsx" -PagosPath "C:\RUTA\DIARIOS\pagos.csv"
```

Notas operativas:

- El caso invalido del script usa una flag inexistente (`--arg-no-existe`) para forzar error deterministico sin depender de contenido de archivos.
- El resultado global queda en `UAT QUICK: PASS/FAIL` y el proceso retorna `0` (pass), `1` (fail), `2` (faltan archivos de entrada).
