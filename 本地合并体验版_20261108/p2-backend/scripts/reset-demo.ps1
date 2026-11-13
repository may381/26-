#requires -Version 7.0
param([switch]$Execute)
. (Join-Path $PSScriptRoot 'local-common.ps1')
$null=Get-DemoContainer
if(-not $Execute){
    Write-Output 'Preview only: clears help/notifications/idempotency/trips/family/profiles/audit in silver_tourism_demo; preserves Flyway and scenic datasets. Stop Java first, then pass -Execute. A backup is mandatory and automatic.'
    return
}
foreach($port in @(8080)){
    if(Test-LocalListener $port){throw 'Stop P2 before resetting. Also stop any Java instance using a custom port.'}
}
$backup=& (Join-Path $PSScriptRoot 'backup.ps1')
if(-not $backup -or -not (Test-Path -LiteralPath $backup) -or (Get-Item -LiteralPath $backup).Length -eq 0){throw 'A valid backup is required.'}
$null=Invoke-DemoMysql @'
START TRANSACTION;
DELETE FROM help_notification;
DELETE FROM help_event;
DELETE FROM idempotency_request;
DELETE FROM trip;
DELETE FROM family_relation;
DELETE FROM elder_profile;
DELETE FROM audit_log;
COMMIT;
'@
Write-Output "Demo business data reset. Backup: $backup"
