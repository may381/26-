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
        throw "$Name failed with exit code $LASTEXITCODE"
    }
    $script:passedSteps++
    Write-Host "PASS: $Name" -ForegroundColor Green
}

try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Python was not found. Install Python 3.12 and add it to PATH."
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw "Node.js was not found. Install Node.js 22 and add it to PATH."
    }

    Push-Location (Join-Path $projectRoot "a1-orchestrator")
    try {
        Invoke-CheckedStep "A1 LangGraph and P2 v3 core tests" {
            python -X utf8 -m unittest discover -p "test_*.py"
        }
        Invoke-CheckedStep "A1 interface consistency check" {
            python -X utf8 verify_doc.py
        }
    }
    finally {
        Pop-Location
    }

    Push-Location (Join-Path $projectRoot "A1new")
    try {
        Invoke-CheckedStep "Unified entry and P2 public API tests" {
            python -X utf8 -m unittest discover -p "test_*.py"
        }
        Invoke-CheckedStep "Browser JavaScript syntax checks" {
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
    Write-Host "ALL PASSED: $passedSteps/4. A1 is ready for integration." -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ""
    Write-Host "PRE-MERGE CHECK FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Fix the first failure above, then run this script again." -ForegroundColor Yellow
    exit 1
}
