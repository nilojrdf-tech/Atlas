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
    --hidden-import pyttsx3.drivers `
    --hidden-import pyttsx3.drivers.sapi5 `
    --exclude-module torch `
    --exclude-module tensorflow `
    --exclude-module sklearn `
    --exclude-module transformers `
    --exclude-module cv2 `
    --exclude-module datasets `
    --exclude-module narwhals `
    --exclude-module dask `
    --exclude-module matplotlib `
    --exclude-module pandas `
    --exclude-module scipy `
    --exclude-module tkinter `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtWebEngineQuick `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtQuick3D `
    --exclude-module PySide6.QtQuickWidgets `
    --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.Qt3DRender `
    --exclude-module PySide6.Qt3DAnimation `
    --exclude-module PySide6.Qt3DExtras `
    --exclude-module PySide6.Qt3DInput `
    --exclude-module PySide6.Qt3DLogic `
    --exclude-module PySide6.QtMultimedia `
    --exclude-module PySide6.QtMultimediaWidgets `
    --exclude-module PySide6.QtPdf `
    --exclude-module PySide6.QtPdfWidgets `
    --exclude-module PySide6.QtSensors `
    --exclude-module PySide6.QtBluetooth `
    --exclude-module PySide6.QtNfc `
    --exclude-module PySide6.QtPositioning `
    --exclude-module PySide6.QtSerialPort `
    --exclude-module PySide6.QtDesigner `
    --exclude-module PySide6.QtCharts `
    --exclude-module PySide6.QtDataVisualization `
    --exclude-module PySide6.QtTest `
    --exclude-module PySide6.QtHelp `
    --exclude-module PySide6.QtSql `
    --exclude-module PySide6.QtSvg `
    --exclude-module PySide6.QtWebChannel `
    --exclude-module PySide6.QtWebSockets `
    run_atlas.py
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $prevPref

if ($exitCode -ne 0) {
    Write-Host "PyInstaller falhou (codigo $exitCode)."
    exit $exitCode
}

Write-Host ""
Write-Host "Executavel gerado em dist\Atlas\Atlas.exe"
