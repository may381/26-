#requires -Version 7.0
. (Join-Path $PSScriptRoot 'local-common.ps1')
$container=Get-DemoContainer
$directory=Join-Path $projectRoot 'backups'
[IO.Directory]::CreateDirectory($directory)|Out-Null
$output=Join-Path $directory ('demo-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fffffff')+'.sql')
$start=[Diagnostics.ProcessStartInfo]::new((Get-LocalDocker))
$start.UseShellExecute=$false; $start.CreateNoWindow=$true
$start.RedirectStandardOutput=$true; $start.RedirectStandardError=$true
foreach($arg in @('exec',$container,'sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump --single-transaction --no-tablespaces --set-gtid-purged=OFF --default-character-set=utf8mb4 -u "$MYSQL_USER" silver_tourism_demo')){$start.ArgumentList.Add($arg)}
$process=[Diagnostics.Process]::Start($start)
$errors=$process.StandardError.ReadToEndAsync()
$file=[IO.File]::Create($output)
try{$process.StandardOutput.BaseStream.CopyTo($file)}finally{$file.Dispose()}
$process.WaitForExit()
if($process.ExitCode -ne 0){throw "Backup failed. Incomplete file retained at $output; do not use it for restore."}
Write-Output $output
