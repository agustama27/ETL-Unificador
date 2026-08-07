@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

set "GIT_AVAILABLE=0"
git -C "%ROOT_DIR%" rev-parse --is-inside-work-tree >nul 2>&1
if not errorlevel 1 set "GIT_AVAILABLE=1"

set "BRANCH_NAME="
if "%GIT_AVAILABLE%"=="1" (
  for /f "usebackq delims=" %%B in (`git -C "%ROOT_DIR%" rev-parse --abbrev-ref HEAD 2^>nul`) do set "BRANCH_NAME=%%B"
)
if not defined BRANCH_NAME set "BRANCH_NAME=unknown"
if /I "%BRANCH_NAME%"=="HEAD" set "BRANCH_NAME=detached-head"

set "COMMIT_SHORT="
if "%GIT_AVAILABLE%"=="1" (
  for /f "usebackq delims=" %%C in (`git -C "%ROOT_DIR%" rev-parse --short HEAD 2^>nul`) do set "COMMIT_SHORT=%%C"
)
if not defined COMMIT_SHORT set "COMMIT_SHORT=unknown"

set "BUILD_DIRTY=false"
if "%GIT_AVAILABLE%"=="1" (
  set "GIT_STATUS_HAS_CHANGES="
  for /f "usebackq delims=" %%S in (`git -C "%ROOT_DIR%" status --porcelain 2^>nul`) do (
    set "GIT_STATUS_HAS_CHANGES=1"
  )
  if defined GIT_STATUS_HAS_CHANGES (
    set "BUILD_DIRTY=true"
    if not "%ALLOW_DIRTY_BUILD%"=="1" (
      echo ERROR: Working tree sucio detectado en "%ROOT_DIR%".
      echo ERROR: Commit/stash/revert cambios antes de compilar para asegurar trazabilidad.
      echo ERROR: Override explicito: set ALLOW_DIRTY_BUILD=1 ^&^& packaging\build.bat
      exit /b 1
    )
  )
)

set "BRANCH_SAFE=%BRANCH_NAME%"
set "BRANCH_SAFE=%BRANCH_SAFE:/=-%"
set "BRANCH_SAFE=%BRANCH_SAFE:\=-%"
if not defined BRANCH_SAFE set "BRANCH_SAFE=unknown"

set "COMMIT_SAFE=%COMMIT_SHORT%"
set "COMMIT_SAFE=%COMMIT_SAFE:/=-%"
set "COMMIT_SAFE=%COMMIT_SAFE:\=-%"
if not defined COMMIT_SAFE set "COMMIT_SAFE=unknown"

if defined DIST_DIR (
  set "DIST_PATH=%DIST_DIR%"
) else (
  set "DIST_PATH=%ROOT_DIR%\dist-%BRANCH_SAFE%-%COMMIT_SAFE%"
)

if defined BUILD_DRY_RUN (
  if "%GIT_AVAILABLE%"=="0" echo WARNING: git no disponible o fuera de repo; branch/commit en unknown.
  echo BRANCH_NAME=%BRANCH_NAME%
  echo COMMIT_SHORT=%COMMIT_SHORT%
  echo BUILD_DIRTY=%BUILD_DIRTY%
  echo BRANCH_SAFE=%BRANCH_SAFE%
  echo COMMIT_SAFE=%COMMIT_SAFE%
  echo DIST_PATH=%DIST_PATH%
  echo BUILD_DRY_RUN activo: no se ejecuta PyInstaller.
  goto :eof
)

if "%GIT_AVAILABLE%"=="0" (
  echo WARNING: git no disponible o fuera de repo; se continua con metadata branch/commit en unknown.
)

echo [1/5] Cleaning previous build artifacts...
if exist "%ROOT_DIR%\build" rmdir /s /q "%ROOT_DIR%\build"
if exist "%DIST_PATH%" rmdir /s /q "%DIST_PATH%"
if exist "%DIST_PATH%\naranjax_etl.exe" (
  echo ERROR: %DIST_PATH%\naranjax_etl.exe sigue bloqueado por otro proceso.
  echo Cerrar app y ejecutar: taskkill /F /IM naranjax_etl.exe
  exit /b 1
)

echo [2/5] Installing packaging dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r "%ROOT_DIR%\requirements-packaging.txt"
if errorlevel 1 goto :error

echo [3/5] Running PyInstaller build...
python -m PyInstaller --noconfirm --clean --distpath "%DIST_PATH%" "%ROOT_DIR%\packaging\naranjax_etl.spec"
if errorlevel 1 goto :error

set "BUILD_TIMESTAMP="
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'"`) do set "BUILD_TIMESTAMP=%%T"
if not defined BUILD_TIMESTAMP set "BUILD_TIMESTAMP=%date% %time%"

set "BUILD_INFO_PATH=%DIST_PATH%\build-info.txt"
(
  echo branch=%BRANCH_NAME%
  echo commit=%COMMIT_SHORT%
  echo timestamp=%BUILD_TIMESTAMP%
  echo dirty=%BUILD_DIRTY%
) > "%BUILD_INFO_PATH%"

echo [4/5] Build output:
if exist "%DIST_PATH%\naranjax_etl.exe" (
  for %%A in ("%DIST_PATH%\naranjax_etl.exe") do set "EXE_SIZE=%%~zA"
  echo EXE: "%DIST_PATH%\naranjax_etl.exe" !EXE_SIZE! bytes
) else (
  echo WARNING: %DIST_PATH%\naranjax_etl.exe was not generated.
)
if exist "%BUILD_INFO_PATH%" echo BUILD INFO: "%BUILD_INFO_PATH%"

echo [5/5] Suggested smoke commands:
echo   "%DIST_PATH%\naranjax_etl.exe"
echo   "%DIST_PATH%\naranjax_etl.exe" --cli --base "C:\ruta\base_mensual.xlsx" --planes "C:\ruta\planes_mensual.xlsx" --pagos "C:\ruta\pagos.csv"
goto :eof

:error
echo Build failed.
exit /b 1
