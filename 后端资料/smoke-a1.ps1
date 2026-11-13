#requires -Version 7.0
param(
    [string]$BaseUrl = 'http://127.0.0.1:8080',
    [string]$A1Url = 'http://127.0.0.1:8093',
    [string]$Text = '请介绍一下杭州西湖有哪些适合慢慢散步的地方。'
)
$ErrorActionPreference = 'Stop'
$BaseUrl = $BaseUrl.TrimEnd('/')
$A1Url = $A1Url.TrimEnd('/')
try {
    $health = Invoke-RestMethod "$A1Url/health" -TimeoutSec 5
} catch {
    throw "无法访问 A1 的 $A1Url/health，请先启动 A1 v3 联调服务。"
}
if ($health.mode -eq 'LOCAL_A1_DOMAIN_COORDINATOR_NOT_P2') {
    throw '当前地址指向 A1 的页面入口，请填写 v3 联调服务地址。'
}

$identity = @{'X-Mock-Actor-Id' = 'u100'; 'X-Mock-Actor-Role' = 'ELDER'}
$headers = $identity.Clone()
$headers['Idempotency-Key'] = 'a1-smoke-' + [guid]::NewGuid()
$body = @{protocolVersion = '3.0'; userId = 'u100'; input = @{text = $Text; attachmentIds = @()}} |
    ConvertTo-Json -Depth 5
$accepted = Invoke-RestMethod "$BaseUrl/api/v3/agent/messages" -Method Post -Headers $headers `
    -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 10
$taskId = $accepted.data.taskId
if (-not $taskId) { throw 'P2 未返回 taskId。' }
$deadline = (Get-Date).AddSeconds(80)
do {
    $task = (Invoke-RestMethod "$BaseUrl/api/v3/agent/tasks/$taskId" -Headers $identity -TimeoutSec 5).data
    if ($task.status -notin 'QUEUED', 'RUNNING') { break }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)
$calls = (Invoke-RestMethod "$BaseUrl/api/v3/agent/tasks/$taskId/invocations" -Headers $identity -TimeoutSec 5).data
if ($task.status -ne 'SUCCEEDED' -or 'a1' -notin $calls.agentId -or
    [string]::IsNullOrWhiteSpace($task.reply.text) -or $task.reply.text -match '^(模拟任务完成|演示追问)') {
    throw "A1 旅游文本任务未通过。taskId=$taskId，状态=$($task.status)，错误码=$($task.error.code)。"
}
Write-Output "PASS: P2 → A1 → P2，taskId=$taskId，状态=$($task.status)。"
