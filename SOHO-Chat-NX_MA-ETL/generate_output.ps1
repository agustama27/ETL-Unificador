# Read source CSV and extract phone numbers
$source = Import-Csv -Path "$env:USERPROFILE\Downloads\NARANJAX_MA_ROMAN_20260429_ALPHA_EVOLTIS.csv" -Delimiter ';'
$phones = @()
foreach ($row in $source) {
    foreach ($col in @('tel_1','tel_2','tel_3')) {
        $val = $row.$col
        if ($val -and $val.Trim() -ne '') {
            $phones += $val.Trim()
        }
    }
}
$phones = $phones | Select-Object -Unique

# Build output in BANCOR format: tel_fijo;tel_celular
$lines = @("tel_fijo;tel_celular")
foreach ($p in $phones) {
    $lines += ";$p"
}

$outputPath = "$env:USERPROFILE\Downloads\NARANJAX_MA_E1KIA_20260429_ALPHA_EVOLTIS.csv"
$lines | Out-File -FilePath $outputPath -Encoding UTF8
Write-Host "Archivo actualizado: $outputPath"
Write-Host "Total numeros: $($phones.Count)"
Write-Host "Numeros:"
$phones | ForEach-Object { Write-Host $_ }
