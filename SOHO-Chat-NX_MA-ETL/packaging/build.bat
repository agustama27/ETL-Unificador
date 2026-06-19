@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

echo [1/5] Cleaning previous build artifacts...
if exist "%ROOT_DIR%\build" rmdir /s /q "%ROOT_DIR%\build"
if exist "%ROOT_DIR%\dist" rmdir /s /q "%ROOT_DIR%\dist"
if exist "%ROOT_DIR%\dist\naranjax_etl.exe" (
  echo ERROR: dist\naranjax_etl.exe sigue bloqueado por otro proceso.
  echo Cerrar app y ejecutar: taskkill /F /IM naranjax_etl.exe
  exit /b 1
)

echo [2/5] Installing packaging dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r "%ROOT_DIR%\requirements-packaging.txt"
if errorlevel 1 goto :error

echo [3/5] Running PyInstaller build...
python -m PyInstaller --noconfirm --clean "%ROOT_DIR%\packaging\naranjax_etl.spec"
if errorlevel 1 goto :error

echo [4/5] Build output:
if exist "%ROOT_DIR%\dist\naranjax_etl.exe" (
  for %%A in ("%ROOT_DIR%\dist\naranjax_etl.exe") do set "EXE_SIZE=%%~zA"
  echo EXE: "%ROOT_DIR%\dist\naranjax_etl.exe" !EXE_SIZE! bytes
) else (
  echo WARNING: dist\naranjax_etl.exe was not generated.
)

echo [5/5] Suggested smoke commands:
echo   "%ROOT_DIR%\dist\naranjax_etl.exe"
echo   "%ROOT_DIR%\dist\naranjax_etl.exe" --cli --base "C:\ruta\base_mensual.xlsx" --planes "C:\ruta\planes_mensual.xlsx" --pagos "C:\ruta\pagos.csv"
goto :eof

:error
echo Build failed.
exit /b 1
