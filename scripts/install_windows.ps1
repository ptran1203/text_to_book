<#
Installs every external tool the pipeline needs, on Windows.
Run from an elevated or normal PowerShell (winget doesn't need admin):

    powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1

Idempotent: re-run any time, it skips what's already there. After it finishes,
open a NEW terminal (so PATH updates from winget take effect) and run
    powershell -File scripts\verify_install.ps1
#>

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ErrorActionPreference = "Stop"
$root  = Split-Path -Parent $PSScriptRoot
$tools = "C:\tools"
New-Item -ItemType Directory -Force -Path $tools | Out-Null

function Get-File($Url, $Dest) {
    if (Test-Path $Dest) { Write-Host "  already have $Dest"; return }
    Write-Host "  downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Dest
}

# ---------------------------------------------------------------- 1. Python
Write-Host "`n== Python packages =="
python -m pip install --upgrade pip
python -m pip install -r "$root\requirements.txt"

# ---------------------------------------------------------------- 2. Tesseract
Write-Host "`n== Tesseract OCR =="
$tesseractExe = "C:\Program Files\Tesseract-OCR\tesseract.exe"
if (-not (Test-Path $tesseractExe)) {
    winget install --id UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements
} else {
    Write-Host "  already installed: $tesseractExe"
}
# Kept in our own folder (not Program Files\...\tessdata) so no admin/UAC is
# needed; 01_ocr.py points tesseract at it via --tessdata-dir.
$tessdataDir = "$tools\tessdata"
New-Item -ItemType Directory -Force -Path $tessdataDir | Out-Null
Get-File "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/vie.traineddata" "$tessdataDir\vie.traineddata"

# ---------------------------------------------------------------- 3. ffmpeg
Write-Host "`n== ffmpeg =="
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
} else {
    Write-Host "  already on PATH"
}

# ---------------------------------------------------------------- 4. piper (offline TTS)
Write-Host "`n== piper TTS =="
$piperDir = "$tools\piper"
New-Item -ItemType Directory -Force -Path $piperDir | Out-Null
$piperZip = "$tools\piper_windows_amd64.zip"
if (-not (Test-Path "$piperDir\piper.exe")) {
    Get-File "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip" $piperZip
    Expand-Archive -Path $piperZip -DestinationPath $tools -Force
    # the zip extracts to a "piper" folder already, but be defensive:
    if (-not (Test-Path "$piperDir\piper.exe") -and (Test-Path "$tools\piper\piper.exe")) {
        Move-Item "$tools\piper\*" $piperDir -Force
    }
} else {
    Write-Host "  already have $piperDir\piper.exe"
}

# Vietnamese voice (vais1000, medium quality)
$voiceBase = "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium"
Get-File "$voiceBase/vi_VN-vais1000-medium.onnx"      "$piperDir\vi_VN-vais1000-medium.onnx"
Get-File "$voiceBase/vi_VN-vais1000-medium.onnx.json" "$piperDir\vi_VN-vais1000-medium.onnx.json"

# ---------------------------------------------------------------- 5. DAISY Pipeline 2
Write-Host "`n== DAISY Pipeline 2 (GUI + CLI installer) =="
$dp2Setup = "$tools\daisy-pipeline-setup-1.12.0.exe"
Get-File "https://github.com/daisy/pipeline-ui/releases/download/1.12.0/daisy-pipeline-setup-1.12.0.exe" $dp2Setup
Write-Host "  Installer downloaded to $dp2Setup"
Write-Host "  This one needs the GUI: run it once manually, click through setup, then close the app." -ForegroundColor Yellow
Write-Host "  Afterwards run scripts\verify_install.ps1 - it locates dp2.exe for you."

Write-Host "`nAll set. Open a NEW terminal, then run:  powershell -File scripts\verify_install.ps1"
