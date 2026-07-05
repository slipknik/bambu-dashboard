# build.ps1
# Script di build per BambuDashboard.
# Esegui con: .\build.ps1  (da PowerShell, nella cartella del progetto)
#
# Produce: dist\BambuDashboard.exe
# Il file di configurazione utente vive separatamente in:
#   %APPDATA%\BambuDashboard\config.json

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Build BambuDashboard ===" -ForegroundColor Cyan

# --- Verifica uv -----------------------------------------------------------
try {
    $uvVer = uv --version 2>&1
    Write-Host "uv trovato: $uvVer"
} catch {
    Write-Host "ERRORE: 'uv' non trovato nel PATH." -ForegroundColor Red
    Write-Host "Installa uv da https://docs.astral.sh/uv/ e riprova."
    exit 1
}

# --- Ambiente virtuale (Python 3.12) ---------------------------------------
Write-Host ""
Write-Host "1/3  Creazione ambiente virtuale (Python 3.12)..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    uv venv --python 3.12 .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "ERRORE creazione venv" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "     (ambiente gia' esistente, lo riuso)"
}

# --- Dipendenze + PyInstaller -----------------------------------------------
Write-Host "2/3  Installazione dipendenze..." -ForegroundColor Yellow
uv pip install -r requirements.txt pyinstaller --python .venv\Scripts\python.exe --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "ERRORE durante pip install" -ForegroundColor Red; exit 1 }

# --- Build ------------------------------------------------------------------
Write-Host "3/3  Build in corso (puo' volerci qualche minuto)..." -ForegroundColor Yellow
.venv\Scripts\pyinstaller.exe bambu_dashboard.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { Write-Host "ERRORE durante PyInstaller" -ForegroundColor Red; exit 1 }

# --- Risultato --------------------------------------------------------------
$exePath = Join-Path $PSScriptRoot "dist\BambuDashboard.exe"
if (Test-Path $exePath) {
    $sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "BUILD COMPLETATA" -ForegroundColor Green
    Write-Host "Eseguibile: $exePath"
    Write-Host "Dimensione: $sizeMB MB"
    
    # Crea il collegamento sul Desktop
    try {
        $desktopPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'), "Bambu Dashboard.lnk")
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($desktopPath)
        $Shortcut.TargetPath = $exePath
        $Shortcut.WorkingDirectory = Join-Path $PSScriptRoot "dist"
        $iconPath = Join-Path $PSScriptRoot "icona4.ico"
        if (Test-Path $iconPath) {
            $Shortcut.IconLocation = $iconPath
        }
        $Shortcut.Save()
        Write-Host "Collegamento creato sul Desktop: $desktopPath" -ForegroundColor Green
    } catch {
        Write-Host "Impossibile creare il collegamento sul Desktop: $_" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Al primo avvio verra' richiesto il login Bambu Lab." -ForegroundColor Cyan
    Write-Host "Il token viene salvato nella cartella locale data\config.json" -ForegroundColor Cyan
    Write-Host "e riusato automaticamente agli avvii successivi." -ForegroundColor Cyan
} else {
    Write-Host "AVVISO: controlla la cartella dist\" -ForegroundColor Yellow
}
