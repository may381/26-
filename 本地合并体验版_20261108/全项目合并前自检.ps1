[CmdletBinding()]
param()

$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path

function Assert-Exit([string]$name) {
    if ($LASTEXITCODE -ne 0) { throw "$name 失败，退出码：$LASTEXITCODE" }
    Write-Host "PASS: $name" -ForegroundColor Green
}

try {
    & (Join-Path $root '合并前自检.ps1')
    Assert-Exit 'A1总智能体与统一入口'

    if (-not (Get-Command mvn -ErrorAction SilentlyContinue)) {
        throw '未找到 Maven，无法测试旅游服务。'
    }
    Push-Location (Join-Path $root 'a1-guide\server')
    try { mvn test; Assert-Exit '旅游服务' } finally { Pop-Location }

    $fraudPython=Join-Path $root 'anti-fraud\backend\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $fraudPython)) {
        throw '反诈虚拟环境不存在；请先运行 anti-fraud\setup-backend.bat。'
    }
    Push-Location (Join-Path $root 'anti-fraud\backend')
    try { & $fraudPython -X utf8 -m pytest -q; Assert-Exit '反诈服务' } finally { Pop-Location }

    Write-Host ''
    Write-Host '总智能体、旅游和反诈全部通过，可进入合并联调。' -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ''
    Write-Host "全项目自检未通过：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
