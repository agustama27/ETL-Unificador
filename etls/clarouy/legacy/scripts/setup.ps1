# setup.ps1 - Script de configuración para soho-ClaroUY-ETL (Windows)
# Ejecutar desde la raíz del proyecto: .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectDir = Join-Path $ProjectRoot "soho-clarouy-encuestas-etl"

Write-Host "=== Setup soho-ClaroUY-ETL ===" -ForegroundColor Cyan
Write-Host "Directorio del proyecto: $ProjectDir" -ForegroundColor Gray

# Verificar que existe el proyecto
if (-not (Test-Path $ProjectDir)) {
    Write-Host "ERROR: No se encuentra soho-clarouy-encuestas-etl en $ProjectDir" -ForegroundColor Red
    exit 1
}

# Activar venv si existe
$VenvPath = Join-Path $ProjectRoot ".venv"
if (Test-Path $VenvPath) {
    Write-Host "Activando entorno virtual..." -ForegroundColor Yellow
    $ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
    & $ActivateScript
}

# Instalar dependencias de back-base
Write-Host "`nInstalando dependencias de back-base..." -ForegroundColor Yellow
$ReqBase = Join-Path $ProjectDir "back-base\requirements.txt"
pip install -r $ReqBase

# Instalar dependencias de back-resultados
Write-Host "`nInstalando dependencias de back-resultados..." -ForegroundColor Yellow
$ReqResultados = Join-Path $ProjectDir "back-resultados\requirements.txt"
pip install -r $ReqResultados

# Crear .env de ejemplo si no existe
$EnvPath = Join-Path $ProjectDir "back-resultados\.env"
if (-not (Test-Path $EnvPath)) {
    Write-Host "`nCreando .env de ejemplo en back-resultados..." -ForegroundColor Yellow
    @"
RETELL_API_KEY=tu_api_key_aqui
USE_ROMAN=true
"@ | Out-File -FilePath $EnvPath -Encoding utf8
    Write-Host "  -> Edita back-resultados\.env y agrega tu RETELL_API_KEY" -ForegroundColor Magenta
} else {
    Write-Host "`n.env ya existe en back-resultados" -ForegroundColor Green
}

Write-Host "`n=== Setup completado ===" -ForegroundColor Green
Write-Host "Para ejecutar back-base:      python soho-clarouy-encuestas-etl\back-base\main.py" -ForegroundColor Gray
Write-Host "Para ejecutar back-resultados: python soho-clarouy-encuestas-etl\back-resultados\main.py" -ForegroundColor Gray
