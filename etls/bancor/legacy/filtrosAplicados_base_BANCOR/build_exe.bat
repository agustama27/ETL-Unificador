@echo off
setlocal

cd /d "%~dp0"

python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Error instalando dependencias.
  exit /b 1
)

pyinstaller --noconfirm --clean --onefile --windowed --name filtrosAplicados_base_BANCOR -p . --hidden-import ui.app --hidden-import ui.phone_compare_tab --hidden-import procesos.pipeline_wfm --hidden-import procesos.phone_compare_service main.py
if errorlevel 1 (
  echo Error generando ejecutable.
  exit /b 1
)

echo.
echo EXE generado en: dist\filtrosAplicados_base_BANCOR.exe
endlocal
