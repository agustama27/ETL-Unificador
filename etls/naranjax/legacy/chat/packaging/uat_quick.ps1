param(
    [string]$ExePath = "dist\\naranjax_etl.exe",
    [string]$BasePath = "C:\\RUTA\\BASE\\base_mensual.xlsx",
    [string]$PlanesPath = "C:\\RUTA\\BASE\\planes_mensual.xlsx",
    [string]$PagosPath = "C:\\RUTA\\DIARIOS\\pagos.csv",
    [string]$Fecha = "20260428",
    [string]$TempRoot = "$env:TEMP\\nx_uat"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

function Check-Exists($path, $label) {
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host "[FAIL] No existe ${label}: $path" -ForegroundColor Red
        return $false
    }
    Write-Host "[OK] ${label}: $path" -ForegroundColor Green
    return $true
}

function Invoke-AndCaptureExitCode {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    try {
        $quotedArgs = $Arguments | ForEach-Object {
            if ($_ -match '[\s"]') {
                '"' + ($_ -replace '"', '\"') + '"'
            } else {
                $_
            }
        }

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $FilePath
        $psi.Arguments = ($quotedArgs -join ' ')
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true

        $process = [System.Diagnostics.Process]::Start($psi)
        $stdout = $process.StandardOutput.ReadToEnd()
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        if ($stdout) { Write-Host $stdout }
        if ($stderr) { Write-Host $stderr -ForegroundColor Yellow }
        return [int]$process.ExitCode
    } catch {
        Write-Host "[FAIL] Error ejecutando comando: $($_.Exception.Message)" -ForegroundColor Red
        return 1
    }
}

function Get-CommonCliArgs {
    return @("--base", $BasePath, "--planes", $PlanesPath, "--pagos", $PagosPath, "--estado", $estadoDir, "--salida", $salidaDir, "--fecha", $Fecha)
}

Step "UAT rapido Fase 4 (sin tocar produccion)"
Write-Host "ExePath   : $ExePath"
Write-Host "BasePath  : $BasePath"
Write-Host "PlanesPath (mensual): $PlanesPath"
Write-Host "PagosPath : $PagosPath"
Write-Host "Fecha     : $Fecha"
Write-Host "TempRoot  : $TempRoot"

$ok = $true
$ok = (Check-Exists $ExePath "ejecutable") -and $ok
$ok = (Check-Exists $BasePath "base") -and $ok
$ok = (Check-Exists $PlanesPath "planes mensual") -and $ok
$ok = (Check-Exists $PagosPath "pagos") -and $ok

if (-not $ok) {
    Write-Host "`nCompleta rutas reales y reintenta. No se ejecuto ningun procesamiento." -ForegroundColor Yellow
    exit 2
}

$estadoDir = Join-Path $TempRoot "estado"
$salidaDir = Join-Path $TempRoot "salida"
New-Item -ItemType Directory -Force -Path $estadoDir | Out-Null
New-Item -ItemType Directory -Force -Path $salidaDir | Out-Null

Step "Caso CLI valido esperado (exit=0)"
$cliPrefix = @("--cli")
$validArgs = $cliPrefix + (Get-CommonCliArgs)
$validExit = Invoke-AndCaptureExitCode -FilePath $ExePath -Arguments $validArgs
if ($validExit -eq 2) {
    Write-Host "[WARN] Exit 2 en caso valido con --cli. Reintentando sin --cli (exe puede estar empaquetado en modo CLI directo)." -ForegroundColor Yellow
    $cliPrefix = @()
    $validArgs = $cliPrefix + (Get-CommonCliArgs)
    $validExit = Invoke-AndCaptureExitCode -FilePath $ExePath -Arguments $validArgs
}
if ($validExit -eq 0) {
    Write-Host "[OK] CLI valido finalizo con exit 0" -ForegroundColor Green
} else {
    Write-Host "[FAIL] CLI valido finalizo con exit $validExit" -ForegroundColor Red
}

Step "Caso CLI invalido esperado (exit!=0)"
$invalidArgs = $cliPrefix + @("--arg-no-existe") + (Get-CommonCliArgs)
$invalidExit = Invoke-AndCaptureExitCode -FilePath $ExePath -Arguments $invalidArgs
if ($invalidExit -ne 0) {
    Write-Host "[OK] CLI invalido finalizo con exit $invalidExit" -ForegroundColor Green
} else {
    Write-Host "[FAIL] CLI invalido finalizo con exit 0" -ForegroundColor Red
}

Step "Resultado"
Write-Host "- Valido   exit: $validExit"
Write-Host "- Invalido exit: $invalidExit"
Write-Host "- Estado temporal: $estadoDir"
Write-Host "- Salida temporal: $salidaDir"

if ($validExit -eq 0 -and $invalidExit -ne 0) {
    Write-Host "`nUAT QUICK: PASS" -ForegroundColor Green
    exit 0
}

Write-Host "`nUAT QUICK: FAIL" -ForegroundColor Red
exit 1
