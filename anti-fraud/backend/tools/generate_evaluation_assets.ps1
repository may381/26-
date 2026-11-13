$ErrorActionPreference = 'Stop'
$assetDir = Join-Path $PSScriptRoot '..\app\evaluation_assets'
New-Item -ItemType Directory -Force -Path $assetDir | Out-Null

Add-Type -AssemblyName System.Drawing
function New-CaseImage([string]$name, [string]$title, [string[]]$lines, [string]$accent) {
  $bitmap = New-Object System.Drawing.Bitmap 1000, 640
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = 'AntiAlias'
  $graphics.Clear([System.Drawing.Color]::FromArgb(18,18,23))
  $accentColor = [System.Drawing.ColorTranslator]::FromHtml($accent)
  $graphics.FillRectangle((New-Object System.Drawing.SolidBrush($accentColor)), 0, 0, 14, 640)
  $titleFont = New-Object System.Drawing.Font('Microsoft YaHei', 30, [System.Drawing.FontStyle]::Bold)
  $bodyFont = New-Object System.Drawing.Font('Microsoft YaHei', 20)
  $smallFont = New-Object System.Drawing.Font('Microsoft YaHei', 14)
  $white = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(240,240,245))
  $muted = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(175,170,185))
  $graphics.DrawString($title, $titleFont, $white, 60, 55)
  $graphics.DrawString('安知标准化测评图片 · 仅用于比赛测试', $smallFont, $muted, 62, 115)
  $y = 190
  foreach ($line in $lines) { $graphics.DrawString($line, $bodyFont, $white, 75, $y); $y += 72 }
  $path = Join-Path $assetDir $name
  $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $graphics.Dispose(); $bitmap.Dispose(); $titleFont.Dispose(); $bodyFont.Dispose(); $smallFont.Dispose(); $white.Dispose(); $muted.Dispose()
}

New-CaseImage 'black-05.png' '案件调查通知' @('你涉嫌洗钱案件', '请保持通话并严格保密', '立即将资金转入指定安全账户') '#b55f62'
New-CaseImage 'black-09.png' '平台客服退款指引' @('会员服务即将连续扣费', '请下载会议软件', '开启屏幕共享办理退款') '#b55f62'
New-CaseImage 'white-02.png' '官方订单详情' @('订单已支付', '物流信息请在官方平台查看', '无需脱离平台或私下付款') '#4b9b78'
New-CaseImage 'white-07.png' '退款进度通知' @('退款已按原支付路径退回', '请登录官方应用查看进度', '客服不会要求共享屏幕') '#4b9b78'

Add-Type -AssemblyName System.Speech
function New-CaseAudio([string]$name, [string]$content) {
  $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $speaker.SelectVoice('Microsoft Huihui Desktop')
  $speaker.SetOutputToWaveFile((Join-Path $assetDir $name))
  $speaker.Speak($content)
  $speaker.Dispose()
}
New-CaseAudio 'black-03.wav' '妈，我换号码了，急需两万元，别回拨，马上转到同事账户。'
New-CaseAudio 'black-10.wav' '我们认识一个月了，我有内幕投资消息，你借钱追加投资一定能赚钱。'
New-CaseAudio 'white-01.wav' '周末下午三点在公园东门见，我们一起散步。'
New-CaseAudio 'white-05.wav' '我已经到家了，晚上不用等我吃饭，记得早点休息。'

Write-Host "Generated evaluation assets in $assetDir"
