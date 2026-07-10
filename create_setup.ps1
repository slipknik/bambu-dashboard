# create_setup.ps1 — compila l'installer Inno Setup da installer.iss
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$exePath = Join-Path $PSScriptRoot "dist\BambuDashboard.exe"
$issPath = Join-Path $PSScriptRoot "installer.iss"

if (-not (Test-Path $exePath)) {
    Write-Host "dist\BambuDashboard.exe non trovato. Esegui prima .\build.ps1" -ForegroundColor Red
    exit 1
}

# Cerca ISCC.exe (Inno Setup 6)
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $isccCmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($isccCmd) { $iscc = $isccCmd.Source }
}
if (-not $iscc) {
    Write-Host "Inno Setup 6 (ISCC.exe) non trovato. Installalo da https://jrsoftware.org/isdl.php" -ForegroundColor Red
    exit 1
}

Write-Host "Compilazione installer con Inno Setup..." -ForegroundColor Yellow
& $iscc $issPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "Compilazione installer fallita (exit code $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}

$setup = Get-ChildItem (Join-Path $PSScriptRoot "dist") -Filter "BambuDashboard_Setup_*.exe" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host "Installer pronto: $($setup.FullName)" -ForegroundColor Green
