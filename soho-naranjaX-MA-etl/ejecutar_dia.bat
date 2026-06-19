@echo off
setlocal

REM Lanzador diario (Windows): doble click o terminal.
REM Uso opcional: ejecutar_dia.bat [argumentos para back-base/ejecutar_dia.py]

echo [INICIO] Ejecutando proceso diario...
python "back-base/ejecutar_dia.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo [FIN] Proceso diario finalizado con error (codigo %EXIT_CODE%).
  pause
  exit /b %EXIT_CODE%
)

echo [FIN] Proceso diario finalizado correctamente.
pause
exit /b 0
