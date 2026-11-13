#requires -Version 7.0
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Join-Path $sourceRoot "github-ready\silver-travel-avatar"
if (Test-Path -LiteralPath $packageRoot) {
    throw "目标目录已存在：$packageRoot。为避免覆盖，请先改名或移走旧整理包。"
}
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

function Copy-SourceTree {
    param([Parameter(Mandatory)][string]$RelativePath)
    $source = Join-Path $sourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) { throw "缺少源目录：$source" }
    $destination = Join-Path $packageRoot $RelativePath
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    $excludedDirectories = @(
        ".git", "__pycache__", ".pytest_cache", "node_modules", "target", "dist",
        ".venv", ".venv-school", ".artifact_tmp", "models", "vendor",
        ".qa-*", ".pytest-*", "test-school-*", ".tmp*"
    )
    $excludedFiles = @(
        "*.pyc", "*.pyo", "*.log", "*.sqlite3", "*.sqlite3-journal", "*.db", "*.db-*", "*.wav",
        "*.pid", "*.tsbuildinfo", "*local.properties", "stress-result.json",
        ".env", ".env.local", ".env.school", ".a1-service-key", "*.zip"
    )
    $arguments = @($source, $destination, "/E", "/R:1", "/W:1", "/XJ", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/XD") +
        $excludedDirectories + @("/XF") + $excludedFiles
    & robocopy @arguments | Out-Null
    if ($LASTEXITCODE -gt 7) { throw "复制失败：$RelativePath（robocopy=$LASTEXITCODE）" }
}

foreach ($directory in @(
    "a1-orchestrator", "A1new", "a1-guide", "外包A30\anti-fraud",
    "后端资料", "交付文档", "设计素材", "时光连UI", "页面样板"
)) {
    Copy-SourceTree $directory
}

foreach ($file in @(
    "比赛启动菜单.cmd", "自检_A1.cmd", "底座契约_v1.md",
    "老人数字分身平台｜项目主线重排版_v2(1).xmind",
    "智能体三人分工与调用关系_单文件图片版.md",
    "智能体三人分工与调用关系_直接打开版.html",
    "智能体三人分工与调用关系_V1.8_后端对齐版.md",
    "A1开发全流程_提示词与讲解手册.md",
    "A1智能体部分开发全流程_提示词与讲解手册.md",
    "A1智能体接口文档_v1.0.md",
    "A1总智能体_LangGraph逐步理解与开发规划.md",
    "UI设计提示词.md"
)) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot $file) -Destination (Join-Path $packageRoot $file)
}

# Runtime travel drafts are user/session data, not repository fixtures.
$travelDrafts = Join-Path $packageRoot "a1-guide\data\travel-drafts"
if (Test-Path -LiteralPath $travelDrafts) {
    Remove-Item -LiteralPath $travelDrafts -Recurse -Force
}

# Keep only QA fixtures referenced by committed browser tests; discard live run reports/screenshots.
$qaDirectory = Join-Path $packageRoot "A1new\qa"
$qaKeep = @("fraud-regression-live.json", "native-plan-save-restore-live.json")
if (Test-Path -LiteralPath $qaDirectory) {
    Get-ChildItem -LiteralPath $qaDirectory -File -Force | Where-Object {
        $_.Name -notin $qaKeep
    } | Remove-Item -Force
}
foreach ($runtimeFile in @(
    "A1new\qa-fraud.png", "A1new\qa-tickets.png",
    "a1-guide\server\planner-live-check.txt", "a1-guide\server\service.log.out",
    "a1-guide\server\service.log.err", "a1-guide\server\SchoolProbe.java",
    "a1-guide\server\school-probe.json"
)) {
    $runtimePath = Join-Path $packageRoot $runtimeFile
    if (Test-Path -LiteralPath $runtimePath) { Remove-Item -LiteralPath $runtimePath -Force }
}

Write-Output $packageRoot
