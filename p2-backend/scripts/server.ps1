param(
    [ValidateSet('verify', 'run', 'wrapper', 'format')]
    [string]$Task = 'verify',
    [string]$JdkHome = 'D:\java develop\jdk21'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$javaExecutable = Join-Path $JdkHome 'bin\java.exe'
if (-not (Test-Path -LiteralPath $javaExecutable)) {
    throw "JDK missing: $JdkHome. Pass -JdkHome to select JDK 21."
}
$previousJavaHome = $env:JAVA_HOME
$previousPath = $env:Path
$previousMysqlPassword = $env:MYSQL_PASSWORD
$previousMysqlPort = $env:MYSQL_PORT
$previousDockerHost = $env:DOCKER_HOST
$previousAmapKey = $env:AMAP_WEB_SERVICE_KEY
$agentVariables = @('AGENTS_MODE','AGENT_A1_URL','AGENT_A2_URL','AGENT_A3_URL','AGENT_A1_API_KEY','AGENT_A2_API_KEY','AGENT_A3_API_KEY')
$previousAgentValues = @{}
foreach ($name in $agentVariables) { $previousAgentValues[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    if ($Task -eq 'verify' -and -not $env:DOCKER_HOST) {
        $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
        $dockerExecutable = if ($dockerCommand) { $dockerCommand.Source } else {
            Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
        }
        if (Test-Path -LiteralPath $dockerExecutable) {
            $dockerEndpoint = & $dockerExecutable context inspect --format '{{.Endpoints.docker.Host}}' 2>$null
            if ($LASTEXITCODE -eq 0 -and $dockerEndpoint) {
                $env:DOCKER_HOST = ($dockerEndpoint | Select-Object -First 1).Trim()
            }
        }
    }
    $envFile = Join-Path $projectRoot '.env'
    if (Test-Path -LiteralPath $envFile) {
        foreach ($line in Get-Content -LiteralPath $envFile) {
            if ($line -match '^(AGENTS_MODE|AGENT_A[123]_URL|AGENT_A[123]_API_KEY)=(.+)$') {
                $name=$Matches[1]; $value=$Matches[2]
                if (-not [Environment]::GetEnvironmentVariable($name,'Process')) {
                    [Environment]::SetEnvironmentVariable($name,$value,'Process')
                }
            }
            if ($line -match '^MYSQL_PASSWORD=(.+)$' -and -not $env:MYSQL_PASSWORD) {
                $env:MYSQL_PASSWORD = $Matches[1]
            } elseif ($line -match '^MYSQL_PORT=([0-9]+)$' -and -not $env:MYSQL_PORT) {
                $env:MYSQL_PORT = $Matches[1]
            } elseif ($line -match '^AMAP_WEB_SERVICE_KEY=(.+)$' -and -not $env:AMAP_WEB_SERVICE_KEY) {
                $env:AMAP_WEB_SERVICE_KEY = $Matches[1]
            }
        }
    }
    $env:JAVA_HOME = $JdkHome
    $env:Path = "$JdkHome\bin;$env:Path"
    Push-Location (Join-Path $projectRoot 'server')
    try {
        $mavenArguments = @('-s', 'settings-local.xml', "-Dmaven.repo.local=$projectRoot\.m2-repository", '-Daether.connector.connectTimeout=10000', '-Daether.connector.requestTimeout=60000', '-B', '-ntp')
        switch ($Task) {
            'verify' { $mavenArguments += 'verify' }
            'run' { $mavenArguments += 'spring-boot:run' }
            'format' { $mavenArguments += 'spotless:apply' }
            'wrapper' { $mavenArguments += @('org.apache.maven.plugins:maven-wrapper-plugin:3.3.4:wrapper', '-Dmaven=3.9.15') }
        }
        if (Test-Path -LiteralPath '.\mvnw.cmd') {
            & .\mvnw.cmd @mavenArguments
        } else {
            & mvn @mavenArguments
        }
        if ($LASTEXITCODE -ne 0) { throw "Maven failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
} finally {
    $env:JAVA_HOME = $previousJavaHome
    $env:Path = $previousPath
    $env:MYSQL_PASSWORD = $previousMysqlPassword
    $env:MYSQL_PORT = $previousMysqlPort
    $env:DOCKER_HOST = $previousDockerHost
    $env:AMAP_WEB_SERVICE_KEY = $previousAmapKey
    foreach ($name in $agentVariables) { [Environment]::SetEnvironmentVariable($name,$previousAgentValues[$name],'Process') }
}
