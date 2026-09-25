# Prepara o ambiente do Atlas: dependencias Python + modelo de voz Vosk pt-BR.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Instalando dependencias Python..."
python -m pip install -r requirements.txt

$modelDir = Join-Path $PSScriptRoot "models\vosk-model-small-pt-0.3"
if (-not (Test-Path $modelDir)) {
    Write-Host "Baixando modelo de reconhecimento de fala (pt-BR, ~32MB)..."
    New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "models") | Out-Null
    $zipPath = Join-Path $PSScriptRoot "models\vosk-model-small-pt-0.3.zip"
    Invoke-WebRequest -Uri "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip" -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath (Join-Path $PSScriptRoot "models") -Force
    Remove-Item $zipPath
    Write-Host "Modelo pronto."
} else {
    Write-Host "Modelo de fala ja esta presente."
}

Write-Host ""
Write-Host "Pronto. Para rodar: .\rodar.ps1"
Write-Host "Na primeira execucao, o Atlas vai pedir sua chave da API do Gemini (https://aistudio.google.com/apikey)."
