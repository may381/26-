param([ValidateSet('school')][string]$Mode='school')
$ErrorActionPreference='Stop'
$workspace=Split-Path $PSScriptRoot -Parent
$manifestPath=Join-Path $workspace '交付文档\release-manifest.json'
if(Test-Path -LiteralPath $manifestPath){
 $manifest=Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
 $jar=Join-Path $workspace $manifest.jar
 if((Get-FileHash -LiteralPath $jar -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.jarSha256){throw 'Release JAR hash mismatch; do not start.'}
}else{$jar=Join-Path $workspace 'target\competition-guide-build\a1-guide-0.1.0.jar'}
if(!(Test-Path -LiteralPath $jar)){throw 'Release JAR missing. Build with guide.build.dir first.'}
$provider='school'
$model='qwen3.8-27b'
Push-Location $PSScriptRoot
try{ & java '-Dfile.encoding=UTF-8' -jar $jar "--ai.model.provider=$provider" "--ai.ollama.model=$model" }finally{Pop-Location}
