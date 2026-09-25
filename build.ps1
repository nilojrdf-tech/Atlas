# Gera o executavel do Atlas para Windows (pasta dist\Atlas\Atlas.exe).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$modelDir = Join-Path $PSScriptRoot "models\vosk-model-small-pt-0.3"
if (-not (Test-Path $modelDir)) {
    Write-Host "Modelo de fala ausente - rode .\instalar.ps1 primeiro."
    exit 1
}

$prevPref = $ErrorActionPreference
$ErrorActionPreference = "Continue"
pyinstaller --noconfirm --windowed --name Atlas `
    --add-data "atlas\assets;atlas\assets" `
    --add-data "models\vosk-model-small-pt-0.3;models\vosk-model-small-pt-0.3" `
    --collect-all vosk `
    --collect-all PySide6 `
    --hidden-import pyttsx3.drivers `
    --hidden-import pyttsx3.drivers.sapi5 `
    run_atlas.py
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $prevPref

if ($exitCode -ne 0) {
    Write-Host "PyInstaller falhou (codigo $exitCode)."
    exit $exitCode
}

Write-Host ""
Write-Host "Executavel gerado em dist\Atlas\Atlas.exe"
