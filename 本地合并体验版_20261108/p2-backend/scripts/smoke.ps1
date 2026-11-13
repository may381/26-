#requires -Version 7.0
# Read-only HTTP smoke for a running local P2; no help creation or persistent profile changes.
$ErrorActionPreference='Stop'
$base='http://127.0.0.1:8080'
$headers=@{'X-Mock-Actor-Id'='u100';'X-Mock-Actor-Role'='ELDER'}
function Assert-Local($Condition,[string]$Message){if(-not $Condition){throw $Message}}
$health=Invoke-RestMethod 'http://127.0.0.1:8081/actuator/health' -TimeoutSec 5
Assert-Local ($health.status -eq 'UP') 'Health check failed.'
$ui=Invoke-WebRequest "$base/swagger-ui/index.html" -TimeoutSec 10
Assert-Local ($ui.StatusCode -eq 200) 'Swagger UI unavailable.'
foreach($path in @('/v3/api-docs','/v3/api-docs/p2')){
    $spec=Invoke-RestMethod "$base$path" -TimeoutSec 30
    $operations=0
    foreach($entry in $spec.paths.PSObject.Properties){
        Assert-Local ($entry.Name.StartsWith('/api/')) 'Internal endpoint leaked into public docs.'
        foreach($method in @('get','post','patch','put','delete')){if($entry.Value.PSObject.Properties.Name -contains $method){$operations++}}
    }
    Assert-Local ($operations -eq 20) "Unexpected public operation count: $operations"
}
$routes=Invoke-RestMethod "$base/api/routes" -Headers $headers -TimeoutSec 10
Assert-Local ($routes.code -eq 'OK' -and $routes.data.routes.Count -eq 3) 'Route provider failed.'
function Invoke-AudioFixture([byte[]]$Bytes){
    $client=[Net.Http.HttpClient]::new()
    $form=[Net.Http.MultipartFormDataContent]::new()
    try{
        foreach($name in $headers.Keys){$client.DefaultRequestHeaders.Add($name,$headers[$name])}
        $client.Timeout=[TimeSpan]::FromSeconds(15)
        $part=[Net.Http.ByteArrayContent]::new($Bytes)
        $part.Headers.ContentType=[Net.Http.Headers.MediaTypeHeaderValue]::new('audio/wav')
        $form.Add($part,'audio','synthetic-test.wav')
        $response=$client.PostAsync("$base/api/speech/transcriptions",$form).GetAwaiter().GetResult()
        try{return @{Status=[int]$response.StatusCode;Body=($response.Content.ReadAsStringAsync().GetAwaiter().GetResult()|ConvertFrom-Json)}}finally{$response.Dispose()}
    }finally{$form.Dispose();$client.Dispose()}
}
# Only a synthetic signature fixture. Not a decodable recording or an ASR quality sample.
$asrResponse=Invoke-AudioFixture ([Text.Encoding]::ASCII.GetBytes('RIFF0000WAVEsynthetic-protocol-test'))
Assert-Local ($asrResponse.Status -eq 200) 'ASR HTTP upload failed.'
$asr=$asrResponse.Body
Assert-Local ($asr.code -eq 'OK' -and $asr.data.text.Contains('演示')) 'ASR mock marker absent.'
$body=@{userId='u100';text=$asr.data.text}|ConvertTo-Json -Compress
$agent=Invoke-RestMethod "$base/api/agent/messages" -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 20
Assert-Local ($agent.code -eq 'OK' -and $agent.data.intent -eq 'tourism' -and $null -eq $agent.data.audioUrl) 'Agent contract failed.'
$ttsBody=@{text=$agent.data.text;speechRate=$agent.data.speechRate}|ConvertTo-Json -Compress
$tts=Invoke-RestMethod "$base/api/speech/syntheses" -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $ttsBody -TimeoutSec 10
Assert-Local ($tts.code -eq 'OK' -and $null -eq $tts.data.audioUrl -and $tts.message.Contains('演示')) 'TTS mock contract failed.'
$unauth=Invoke-WebRequest "$base/api/routes" -SkipHttpErrorCheck -TimeoutSec 5
Assert-Local ($unauth.StatusCode -eq 401) 'Unauthenticated request should be rejected.'
$foreign=Invoke-WebRequest "$base/api/speech/syntheses?userId=u101" -Method Post -Headers $headers -ContentType 'application/json' -Body '{"text":"test","speechRate":1}' -SkipHttpErrorCheck -TimeoutSec 5
Assert-Local ($foreign.StatusCode -eq 403) 'Cross-user speech request should be rejected.'
$oversized=Invoke-AudioFixture ([byte[]]::new(10*1024*1024+1))
Assert-Local ($oversized.Status -eq 400 -and $oversized.Body.code -eq 'INVALID_ARGUMENT') 'Multipart size limit should return the contract error.'
Write-Output 'PASS: health, Swagger UI, 20 public operations, routes, mock ASR -> Agent -> mock TTS, oversized upload 400, 401 and cross-user 403. No persistent business data written.'
