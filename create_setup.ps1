# create_setup.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$distDir = Join-Path $PSScriptRoot "dist"
$exePath = Join-Path $distDir "BambuDashboard.exe"
$zipPath = Join-Path $distDir "BambuDashboard_Setup.zip"

if (Test-Path $exePath) {
    Write-Host "Creazione pacchetto di Setup ZIP..." -ForegroundColor Yellow
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path $exePath -DestinationPath $zipPath -Force
    Write-Host "Pacchetto Setup pronto: $zipPath" -ForegroundColor Green
}
