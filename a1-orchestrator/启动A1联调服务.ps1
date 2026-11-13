$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$serviceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $serviceDir

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "未找到 python，请先安装 Python 3.8+ 并加入 PATH。"
}

python -c "import langgraph" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "缺少 LangGraph，请先运行：python -m pip install -r requirements.txt"
}

$keyFile = Join-Path $serviceDir ".a1-service-key"
if (-not $env:A1_SERVICE_KEY -and -not (Test-Path -LiteralPath $keyFile)) {
    $secureKey = Read-Host "请输入与 P2 的 AGENT_A1_API_KEY 相同的联调密钥（不会写入磁盘）" -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $env:A1_SERVICE_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    if (-not $env:A1_SERVICE_KEY) {
        throw "联调密钥不能为空。"
    }
}

$port = if ($env:A1_PORT) { [int]$env:A1_PORT } else { 8093 }
$env:A1_BIND = if ($env:A1_BIND) { $env:A1_BIND } else { "0.0.0.0" }
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    throw "端口 $port 已被进程 $($listener.OwningProcess) 占用，请先确认该进程是否已经是 A1 服务。"
}

Write-Host "正在启动 A1 v3 联调服务；本机探活：http://127.0.0.1:$port/health"
Write-Host "跨电脑联调已监听 $($env:A1_BIND):$port；P2 应填写本机局域网或虚拟局域网 IP。"
Write-Host "保持此窗口运行；按 Ctrl+C 停止。"
python -X utf8 service.py
