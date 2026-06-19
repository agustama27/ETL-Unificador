@echo off
setlocal EnableExtensions EnableDelayedExpansion

set APP_NAME=naranjax_mt_etl
set APP_PRODUCT_NAME=NaranjaX MT ETL
set APP_COMPANY_NAME=SOHO
set APP_FILE_DESCRIPTION=ETL de telefonos NaranjaX MT
set APP_COPYRIGHT=Copyright ^(c^) SOHO
set APP_VERSION=1.0.0.0
set APP_ICON=%~dp0assets\app.ico
set APP_VERSION_FILE=%TEMP%\%APP_NAME%-version-info.txt

for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set BRANCH_NAME=%%i
if "%BRANCH_NAME%"=="" set BRANCH_NAME=unknown
if /I "%BRANCH_NAME%"=="HEAD" set BRANCH_NAME=detached-head

for /f "delims=" %%i in ('git rev-parse --short HEAD 2^>nul') do set COMMIT_SHORT=%%i
if "%COMMIT_SHORT%"=="" set COMMIT_SHORT=unknown

set BUILD_DIRTY=false
for /f "delims=" %%i in ('git status --porcelain 2^>nul') do set BUILD_DIRTY=true

set BRANCH_SAFE=%BRANCH_NAME:/=-%
set BRANCH_SAFE=%BRANCH_SAFE:\=-%
set COMMIT_SAFE=%COMMIT_SHORT:/=-%
set COMMIT_SAFE=%COMMIT_SAFE:\=-%

set DIST_PATH=dist-%BRANCH_SAFE%-%COMMIT_SAFE%
if not "%DIST_DIR%"=="" set DIST_PATH=%DIST_DIR%

if "%BUILD_DRY_RUN%"=="1" goto dry_run

if "%BUILD_DIRTY%"=="true" if not "%ALLOW_DIRTY_BUILD%"=="1" (
  echo ERROR: Working tree dirty. Set ALLOW_DIRTY_BUILD=1 to override.
  exit /b 1
)

:dry_run
if "%BUILD_DRY_RUN%"=="1" (
  echo APP_NAME=%APP_NAME%
  echo BRANCH_NAME=%BRANCH_NAME%
  echo COMMIT_SHORT=%COMMIT_SHORT%
  echo BUILD_DIRTY=%BUILD_DIRTY%
  echo DIST_PATH=%DIST_PATH%
  echo APP_ICON=%APP_ICON%
  echo APP_VERSION=%APP_VERSION%
  exit /b 0
)

rmdir /s /q build 2>nul
rmdir /s /q "%DIST_PATH%" 2>nul

set APP_VERSION_FILE=

pyinstaller --noconfirm --clean --distpath "%DIST_PATH%" packaging\naranjax_mt_etl.spec
if errorlevel 1 exit /b 1

powershell -NoProfile -Command "$ts=(Get-Date).ToString('s'); @('branch=%BRANCH_NAME%','commit=%COMMIT_SHORT%','timestamp='+$ts,'dirty=%BUILD_DIRTY%') | Set-Content -Encoding UTF8 '%DIST_PATH%\build-info.txt'"

echo.
echo Build generado: %DIST_PATH%\%APP_NAME%.exe
echo Smoke tests:
echo   1) Doble clic al .exe
echo   2) %DIST_PATH%\%APP_NAME%.exe --cli --base C:\ruta\archivo.txt --salida C:\TEMP\out --estado C:\TEMP\estado
