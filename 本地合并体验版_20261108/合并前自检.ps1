[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$passedSteps = 0

function Invoke-CheckedStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name 失败，退出码：$LASTEXITCODE"
    }
    $script:passedSteps++
    Write-Host "PASS: $Name" -ForegroundColor Green
}

try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "未找到 Python，请先安装 Python 3.12，并将 python 加入 PATH。"
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw "未找到 Node.js，请先安装 Node.js 22，并将 node 加入 PATH。"
    }

    Push-Location (Join-Path $projectRoot "a1-orchestrator")
    try {
        Invoke-CheckedStep "A1 LangGraph 与 P2 v3 核心测试" {
            python -X utf8 -m unittest discover -p "test_*.py"
        }
        Invoke-CheckedStep "A1 接口文档与实现一致性检查" {
            python -X utf8 verify_doc.py
        }
    }
    finally {
        Pop-Location
    }

    Push-Location (Join-Path $projectRoot "A1new")
    try {
        Invoke-CheckedStep "统一入口与 P2 公开接口测试" {
            python -X utf8 -m unittest discover -p "test_*.py"
        }
        Invoke-CheckedStep "关键浏览器脚本语法检查" {
            node --check app.js
            if ($LASTEXITCODE -ne 0) { return }
            node --check fraud-ui.js
            if ($LASTEXITCODE -ne 0) { return }
            node --check native-tourism.js
            if ($LASTEXITCODE -ne 0) { return }
            node --check tools.js
        }
    }
    finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "全部通过：$passedSteps/4。当前 A1 代码可进入合并与联调。" -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ""
    Write-Host "合并前自检未通过：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "请先修复上方第一处失败，再重新运行本脚本。" -ForegroundColor Yellow
    exit 1
}
