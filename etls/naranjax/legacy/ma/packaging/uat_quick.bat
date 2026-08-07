@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%uat_quick.ps1" %*
exit /b %ERRORLEVEL%
