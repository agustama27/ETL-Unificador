@echo off
setlocal

cd /d "%~dp0"

python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Error instalando dependencias.
  exit /b 1
)

REM config_quita.py / config_preventa.py son los modulos de campania. Viven en
REM back-base\procesos (unica fuente de verdad de ambas salidas ROMAN) y se copian a
REM la raiz del bundle porque pipeline_wfm los importa POR NOMBRE. NO son opcionales:
REM config_quita lleva calcular_quita, que antes se cargaba desde base_generator.py
REM con un loader por path y en el exe defaulteaba en silencio a aplica_quita="no".
pyinstaller --noconfirm --clean --onefile --windowed --name filtrosAplicados_base_BANCOR -p . --hidden-import ui.app --hidden-import ui.phone_compare_tab --hidden-import procesos.pipeline_wfm --hidden-import procesos.phone_compare_service --add-data "..\back-base\procesos\config_quita.py;." --add-data "..\back-base\procesos\config_preventa.py;." main.py
if errorlevel 1 (
  echo Error generando ejecutable.
  exit /b 1
)

echo.
echo EXE generado en: dist\filtrosAplicados_base_BANCOR.exe
endlocal
