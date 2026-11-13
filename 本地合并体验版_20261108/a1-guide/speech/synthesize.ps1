param(
  [string]$TextFile,
  [string]$OutputFile,
  [int]$Rate=0,
  [int]$Volume=100,
  [string]$Voice=''
)
$ErrorActionPreference='Stop'
$text=[IO.File]::ReadAllText($TextFile,[Text.Encoding]::UTF8)
if([string]::IsNullOrWhiteSpace($text)){throw 'empty text'}
if(Test-Path -LiteralPath $OutputFile){Remove-Item -LiteralPath $OutputFile -Force}

# 自然语音优先：Windows「设置 > 时间和语言 > 语音 > 添加语音」装好后会被自动选中
$naturalOrder=@('Xiaoxiao','Xiaoyi','Yunxi','Yunyang','Xiaochen','Yunjian','Xiaobei','Xiaoshuang','Yunxia')
$classicOrder=@('Yaoyao','Huihui','Kangkang')

function Match-Voice($list,$want){
  foreach($n in @($want)){
    $hit=@($list|Where-Object{$_.Name -match "(?i)(^|[^a-zA-Z])$n([^a-zA-Z]|$)" -or $_.DisplayName -match "(?i)(^|[^a-zA-Z])$n([^a-zA-Z]|$)"})
    if($hit.Count -gt 0){return $hit[0]}
  }
  return $null
}

# ---- 1) OneCore / WinRT：能用上「设置」里装的自然语音 ----
try{
  Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction Stop
  $SynthT=[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]
  $StreamT=[Windows.Media.SpeechSynthesis.SpeechSynthesisStream,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]
  $synth=[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]::new()
  $zh=@($SynthT::AllVoices|Where-Object{$_.Language -like 'zh*'})
  $pick=$null
  if(-not [string]::IsNullOrWhiteSpace($Voice)){$pick=Match-Voice $zh $Voice}
  if($null -eq $pick){$pick=Match-Voice $zh $naturalOrder}
  if($null -eq $pick){$pick=Match-Voice $zh $classicOrder}
  if($null -eq $pick -and $zh.Count -gt 0){$pick=$zh[0]}
  if($null -eq $pick){$synth.Dispose();throw 'no zh-CN voice'}
  $voiceName=$pick.DisplayName
  $synth.Voice=$pick
  $op=$synth.SynthesizeTextToStreamAsync($text)
  $asTask=[System.WindowsRuntimeSystemExtensions].GetMethods()|Where-Object{$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -like 'IAsyncOperation*'}|Select-Object -First 1
  $stream=$asTask.MakeGenericMethod(@($StreamT)).Invoke($null,@($op)).GetAwaiter().GetResult()
  try{
    $stream.Seek(0)
    $net=[System.IO.WindowsRuntimeStreamExtensions].GetMethods()|Where-Object{$_.Name -eq 'AsStreamForRead' -and $_.GetParameters().Count -eq 1}|Select-Object -First 1
    $reader=$net.Invoke($null,@($stream))
    $fs=[IO.File]::Create($OutputFile)
    try{$reader.CopyTo($fs)}finally{$fs.Dispose();$reader.Dispose()}
  }finally{$stream.Dispose();$synth.Dispose()}
  if((Get-Item -LiteralPath $OutputFile).Length -gt 44){
    Write-Output ("VOICE="+$voiceName)
    return
  }
}catch{}
Remove-Item -LiteralPath $OutputFile -Force -ErrorAction SilentlyContinue

# ---- 2) 回退：经典 SAPI5 语音 ----
Add-Type -AssemblyName System.Speech
$s=New-Object System.Speech.Synthesis.SpeechSynthesizer
try{
  $installed=@($s.GetInstalledVoices()|Where-Object{$_.Enabled}|ForEach-Object{$_.VoiceInfo})
  if($installed.Count -eq 0){throw 'no installed voice'}
  $zh2=@($installed|Where-Object{$_.Culture.Name -like 'zh*'})
  $chosen=$null
  if(-not [string]::IsNullOrWhiteSpace($Voice)){
    $chosen=Match-Voice $zh2 $Voice
    if($null -eq $chosen){$chosen=Match-Voice $installed $Voice}
  }
  if($null -eq $chosen){$chosen=Match-Voice $zh2 $classicOrder}
  if($null -eq $chosen -and $zh2.Count -gt 0){$chosen=$zh2[0]}
  if($null -eq $chosen){$chosen=$installed[0]}
  $s.SelectVoice($chosen.Name)
  $s.Rate=[Math]::Max(-10,[Math]::Min(10,$Rate))
  $s.Volume=[Math]::Max(0,[Math]::Min(100,$Volume))
  $s.SetOutputToWaveFile($OutputFile)
  $s.Speak($text)
  Write-Output ("VOICE="+$chosen.Name)
}finally{$s.Dispose()}
