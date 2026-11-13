#requires -Version 7.0
param([string]$DataRoot='D:\挑战杯\p2-speech-local', [int]$Port=18010)
$ErrorActionPreference='Stop'
$python=Join-Path $DataRoot '.venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $python)){throw "Missing speech environment: $python"}
$previousModels=$env:SPEECH_MODEL_DIR
try {
    $env:SPEECH_MODEL_DIR='models'
    Push-Location $DataRoot
    try {
        & $python -m uvicorn service:app --app-dir $PSScriptRoot --host 127.0.0.1 --port $Port --workers 1
        if($LASTEXITCODE -ne 0){throw "Speech service exited: $LASTEXITCODE"}
    } finally {Pop-Location}
} finally {$env:SPEECH_MODEL_DIR=$previousModels}
