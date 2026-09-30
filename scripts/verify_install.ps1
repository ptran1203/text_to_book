<#
Checks every external tool the pipeline needs and prints the exact paths to put
in config\pipeline.yaml. Run in a NEW terminal after install_windows.ps1 (and
after manually clicking through the DAISY Pipeline 2 GUI installer once).

    powershell -ExecutionPolicy Bypass -File scripts\verify_install.ps1
#>

function Check($label, $ok, $detail) {
    $mark = if ($ok) { "OK  " } else { "MISSING" }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host ("{0,-8} {1,-10} {2}" -f $mark, $label, $detail) -ForegroundColor $color
}

Write-Host "== Python packages =="
python -c "import fitz, pytesseract, PIL, numpy, yaml; print('  pymupdf/pytesseract/pillow/numpy/pyyaml OK')" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "  MISSING - run: pip install -r requirements.txt" -ForegroundColor Red }

Write-Host "`n== VietOCR (Vietnamese recognition) =="
python -c "import torch, vietocr; print('  torch', torch.__version__, '| cuda', torch.cuda.is_available())" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  MISSING - pip install vietocr, and torch (CPU: pip install torch --index-url https://download.pytorch.org/whl/cpu)" -ForegroundColor Red
}

Write-Host "`n== Tesseract =="
$tess = "C:\Program Files\Tesseract-OCR\tesseract.exe"
Check "tesseract" (Test-Path $tess) $tess
$vie = "C:\tools\tessdata\vie.traineddata"
Check "vie.traineddata" (Test-Path $vie) $vie

Write-Host "`n== ffmpeg =="
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
Check "ffmpeg" ($null -ne $ffmpeg) $(if ($ffmpeg) { $ffmpeg.Source } else { "not on PATH - open a NEW terminal after install" })

Write-Host "`n== piper =="
$piper = "C:\tools\piper\piper.exe"
Check "piper.exe" (Test-Path $piper) $piper
$voice = "C:\tools\piper\vi_VN-vais1000-medium.onnx"
Check "voice model" (Test-Path $voice) $voice

Write-Host "`n== DAISY Pipeline 2 (dp2) =="
$dp2 = Get-Command dp2 -ErrorAction SilentlyContinue
if ($dp2) {
    Check "dp2" $true $dp2.Source
} else {
    $found = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs","C:\Program Files","C:\Program Files (x86)" `
        -Recurse -Filter "dp2.exe" -ErrorAction SilentlyContinue -Depth 6 | Select-Object -First 1
    if ($found) {
        Check "dp2" $true "$($found.FullName)   <- put this in config/pipeline.yaml step_07_validate.dp2"
    } else {
        Check "dp2" $false "not found - install scripts\daisy-pipeline-setup-1.12.0.exe (GUI) first"
    }
}

Write-Host "`nDone. Fix any MISSING line above, then re-run this script."
