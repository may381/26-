param([string]$InputFile)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Speech
$r=New-Object System.Speech.Recognition.SpeechRecognitionEngine([Globalization.CultureInfo]::GetCultureInfo('zh-CN'))
try{
 $r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
 $r.SetInputToWaveFile($InputFile)
 $parts=New-Object 'System.Collections.Generic.List[string]'
 $scores=New-Object 'System.Collections.Generic.List[double]'
 while($true){try{$result=$r.Recognize()}catch [System.Management.Automation.MethodInvocationException]{if($_.Exception.InnerException -is [InvalidOperationException]){break};throw};if($null -eq $result){break};if($result.Confidence -ge 0.25){$parts.Add($result.Text);$scores.Add($result.Confidence)}}
 $confidence=0;if($scores.Count -gt 0){$confidence=($scores|Measure-Object -Average).Average}
 @{text=($parts -join '');confidence=$confidence}|ConvertTo-Json -Compress
}finally{$r.Dispose()}


