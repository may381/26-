#requires -Version 7.0
param([switch]$PythonMock,[string]$JdkHome='D:\java develop\jdk21')
. (Join-Path $PSScriptRoot 'local-common.ps1')
& (Join-Path $PSScriptRoot 'init-env.ps1')
$docker=Get-LocalDocker
& $docker compose --project-name silver-tourism-p2-baseline --project-directory $projectRoot up -d --wait mysql
if($LASTEXITCODE -ne 0){throw 'Demo MySQL did not become healthy.'}
$pythonProcess=$null; $previousMode=$env:AGENTS_MODE
try {
    if($PythonMock){
        # Do not take over ports owned by unrelated processes.
        foreach($port in @(18001,18002,18003)){
            if(Test-LocalListener $port){throw "Port $port is already in use."}
        }
        $python=(Get-Command python -ErrorAction Stop).Source
        $runtime=Join-Path $projectRoot 'runtime'
        [IO.Directory]::CreateDirectory($runtime)|Out-Null
        $pythonProcess=Start-Process -FilePath $python -ArgumentList @('agents/mock/server.py') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'python-mock.out.log') -RedirectStandardError (Join-Path $runtime 'python-mock.err.log')
        $ready=$false
        for($attempt=0;$attempt -lt 30;$attempt++){
            if($pythonProcess.HasExited){throw 'Python mock exited; inspect runtime/python-mock.err.log.'}
            try {
                foreach($port in @(18001,18002,18003)){ $null=Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 1 }
                $ready=$true; break
            }catch{Start-Sleep -Milliseconds 200}
        }
        if(-not $ready){throw 'Python mock startup timed out.'}
        $env:AGENTS_MODE='http'
    }
    Write-Output 'Starting P2. Swagger: http://127.0.0.1:8080/swagger-ui/index.html . Ctrl+C stops Java and the Python child started here.'
    & (Join-Path $PSScriptRoot 'server.ps1') -Task run -JdkHome $JdkHome
} finally {
    $env:AGENTS_MODE=$previousMode
    if($pythonProcess -and -not $pythonProcess.HasExited){$pythonProcess.Kill();$pythonProcess.WaitForExit()}
}
