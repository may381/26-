#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
function Test-LocalListener([int]$Port) {
    return @([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object Port -eq $Port).Count -gt 0
}
function Get-LocalDocker {
    $command = Get-Command docker -ErrorAction SilentlyContinue
    $candidate = if ($command) { $command.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
    if (-not (Test-Path -LiteralPath $candidate)) { throw 'Docker CLI missing. Install/open Docker Desktop first.' }
    return $candidate
}
function Get-DemoContainer {
    $docker = Get-LocalDocker
    $container = & $docker compose --project-name silver-tourism-p2-baseline --project-directory $projectRoot ps -q mysql
    if ($LASTEXITCODE -ne 0 -or -not $container -or @($container).Count -ne 1) { throw 'The dedicated demo MySQL container must be running.' }
    $details = (& $docker inspect $container | ConvertFrom-Json)[0]
    if ($details.Config.Labels.'com.docker.compose.project' -ne 'silver-tourism-p2-baseline' -or
        $details.Config.Labels.'com.docker.compose.service' -ne 'mysql' -or
        $details.Config.Env -notcontains 'MYSQL_DATABASE=silver_tourism_demo' -or
        $details.Config.Env -notcontains 'MYSQL_USER=silver_app') { throw 'Refusing unexpected database target.' }
    return $container.Trim()
}
function Invoke-DemoMysql([string]$Sql) {
    $container = Get-DemoContainer
    $start = [Diagnostics.ProcessStartInfo]::new((Get-LocalDocker))
    $start.UseShellExecute=$false; $start.CreateNoWindow=$true
    $start.RedirectStandardInput=$true; $start.RedirectStandardOutput=$true; $start.RedirectStandardError=$true
    foreach($arg in @('exec','-i',$container,'sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" exec mysql --default-character-set=utf8mb4 -u "$MYSQL_USER" silver_tourism_demo')) { $start.ArgumentList.Add($arg) }
    $process = [Diagnostics.Process]::Start($start)
    $outTask=$process.StandardOutput.ReadToEndAsync(); $errTask=$process.StandardError.ReadToEndAsync()
    $process.StandardInput.Write($Sql); $process.StandardInput.Close(); $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw 'Demo database operation failed; no credentials are printed.' }
    return $outTask.GetAwaiter().GetResult()
}
