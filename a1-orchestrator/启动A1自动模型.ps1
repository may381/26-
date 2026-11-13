param(
    [ValidateSet('auto', 'school', 'offline')]
    [string]$Mode = 'auto',
    [string]$OfflineModel = 'qwen3:4b',
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$serviceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $serviceDir

$schoolBase = 'http://10.138.50.151:8000'
$offlineBase = 'http://127.0.0.1:11434'

function Test-ModelServer([string]$Base) {
    try {
        $null = Invoke-RestMethod "$Base/v1/models" -TimeoutSec 4
        return $true
    } catch {
        return $false
    }
}

function Start-OllamaIfNeeded {
    if (Test-ModelServer $offlineBase) { return }
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        throw '未安装 Ollama，无法使用离线模型。'
    }
    Start-Process -FilePath $ollama.Source -ArgumentList 'serve' -WindowStyle Hidden
    foreach ($attempt in 1..15) {
        Start-Sleep -Seconds 1
        if (Test-ModelServer $offlineBase) { return }
    }
    throw 'Ollama 未能在 127.0.0.1:11434 启动。'
}

$selected = $Mode
if ($Mode -eq 'auto') {
    $selected = if (Test-ModelServer $schoolBase) { 'school' } else { 'offline' }
}

if ($selected -eq 'school') {
    if (-not (Test-ModelServer $schoolBase)) {
        throw '校内模型不可访问，请连接校园网/学校 VPN，或使用 -Mode offline。'
    }
    $env:A1_MODEL_URL = "$schoolBase/v1/chat/completions"
    $env:A1_MODEL_NAME = 'qwen3.8-27b'
    Write-Host 'A1 模型：校内 qwen3.8-27b'
} else {
    Start-OllamaIfNeeded
    $tags = (Invoke-RestMethod "$offlineBase/api/tags" -TimeoutSec 10).models
    if (-not ($tags | Where-Object { $_.name -eq $OfflineModel -or $_.model -eq $OfflineModel })) {
        throw "尚未下载离线模型 $OfflineModel。网络可用时先执行：ollama pull $OfflineModel"
    }
    $env:A1_MODEL_URL = "$offlineBase/v1/chat/completions"
    $env:A1_MODEL_NAME = $OfflineModel
    Write-Host "A1 模型：本机 Ollama $OfflineModel（断网可用）"
}

$env:A1_MODEL_TIMEOUT_SECONDS = '45'
$env:A1_TOURISM_URL = if ($env:A1_TOURISM_URL) { $env:A1_TOURISM_URL } else { 'http://127.0.0.1:8091' }
$env:A1_FRAUD_URL = if ($env:A1_FRAUD_URL) { $env:A1_FRAUD_URL } else { 'http://127.0.0.1:8000' }

if ($CheckOnly) {
    Write-Host "模型服务检查通过：$($env:A1_MODEL_URL)"
    exit 0
}

& (Join-Path $serviceDir '启动A1联调服务.ps1')

