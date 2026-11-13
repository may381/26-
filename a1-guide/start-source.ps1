$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$serverDir = Join-Path $PSScriptRoot 'server'
if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw '未找到 Java；旅游服务需要 JDK 17。'
}
if (-not (Get-Command mvn -ErrorAction SilentlyContinue)) {
    throw '未找到 Maven；请安装 Maven 3.9+ 并加入 PATH。'
}

$env:SERVER_ADDRESS = if ($env:SERVER_ADDRESS) { $env:SERVER_ADDRESS } else { '127.0.0.1' }
$env:PORT = if ($env:PORT) { $env:PORT } else { '8091' }
Write-Host "正在从源码启动旅游服务：http://127.0.0.1:$($env:PORT)/"
Write-Host '首次运行需要 Maven 下载依赖；保持窗口运行，按 Ctrl+C 停止。'
Push-Location $serverDir
try {
    mvn -DskipTests spring-boot:run
    if ($LASTEXITCODE -ne 0) { throw "旅游服务启动失败，Maven 退出码：$LASTEXITCODE" }
}
finally {
    Pop-Location
}
