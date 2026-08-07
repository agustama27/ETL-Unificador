@echo off
setlocal

cd /d "%~dp0"

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Error instalando dependencias.
  exit /b 1
)

pyinstaller --noconfirm --clean bancor_roman_only.spec
if errorlevel 1 (
  echo Error generando ejecutable.
  exit /b 1
)

echo.
echo EXE generado en: dist\Resultados_BANCOR.exe
endlocal
