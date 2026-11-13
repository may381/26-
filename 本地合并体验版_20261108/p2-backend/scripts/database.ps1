param([ValidateSet('up', 'status', 'stop')][string]$Task = 'status')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerExecutable = if ($dockerCommand) { $dockerCommand.Source } else {
    Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
}
if (-not (Test-Path -LiteralPath $dockerExecutable)) { throw 'Docker CLI not found. Start/install Docker Desktop first.' }
$previousPath = $env:Path
try {
    $env:Path = "$(Split-Path -Parent $dockerExecutable);$env:Path"
    Push-Location $projectRoot
    try {
        switch ($Task) {
            'up' { & $dockerExecutable compose -p silver-tourism-p2-baseline up -d --wait mysql }
            'status' { & $dockerExecutable compose -p silver-tourism-p2-baseline ps }
            'stop' { & $dockerExecutable compose -p silver-tourism-p2-baseline stop mysql }
        }
        if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
} finally { $env:Path = $previousPath }
