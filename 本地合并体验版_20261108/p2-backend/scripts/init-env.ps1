#requires -Version 7.0
# Existing values, including AMap key, are preserved.
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$path=Join-Path $root '.env'
$lines=if(Test-Path -LiteralPath $path){@(Get-Content -LiteralPath $path)}else{@()}
$changed=$false
$defaults=[ordered]@{
    MYSQL_PASSWORD=[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    MYSQL_ROOT_PASSWORD=[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    MYSQL_PORT='3308'; AMAP_WEB_SERVICE_KEY=''; AGENTS_MODE='mock'
    AGENT_A1_URL='http://127.0.0.1:18001'; AGENT_A2_URL='http://127.0.0.1:18002'; AGENT_A3_URL='http://127.0.0.1:18003'
    AGENT_A1_API_KEY=[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    AGENT_A2_API_KEY=[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    AGENT_A3_API_KEY=[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
}
foreach($name in $defaults.Keys){
    $found=@($lines | Where-Object { $_ -match ('^'+[regex]::Escape($name)+'=') })
    if($found.Count -eq 0){ $lines += "$name=$($defaults[$name])"; $changed=$true }
}
if($changed){[IO.File]::WriteAllLines($path,[string[]]$lines,[Text.UTF8Encoding]::new($false))}
Write-Output 'Local .env is ready. Existing values were preserved; secrets are not displayed.'
