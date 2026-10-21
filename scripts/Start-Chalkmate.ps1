param([switch]$SkipBuild)
. (Join-Path $PSScriptRoot 'Local-Common.ps1')
Set-Location -LiteralPath $ChalkmateRoot
New-Item -ItemType Directory -Path $ChalkmateRuntime -Force | Out-Null
$python = Join-Path $ChalkmateRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python) -or !(Test-Path -LiteralPath (Join-Path $ChalkmateRoot 'node_modules'))) {
    throw 'Install dependencies first; see README.md local setup'
}
$apiAddress = 'http://127.0.0.1:8100'
$apiRunning = Test-ChalkmateHealth $apiAddress 'chalkmate-api'
$webPort = 3000
if (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue) {
    if (!(Test-ChalkmateHealth 'http://localhost:3000' 'chalkmate-web')) { $webPort = 3001 }
}
$webAddress = "http://localhost:$webPort"
$webRunning = Test-ChalkmateHealth $webAddress 'chalkmate-web'
if (!$webRunning -and (Get-NetTCPConnection -LocalPort $webPort -State Listen -ErrorAction SilentlyContinue)) {
    throw "Port $webPort is occupied; no existing application was stopped"
}
if (!$apiRunning -and (Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue)) {
    throw 'Port 8100 is occupied; no existing application was stopped'
}
if ($apiRunning -and !$webRunning) {
    throw 'An existing API is running. Stop it in its terminal before selecting a new web origin.'
}
$env:WEB_ORIGIN = $webAddress
Invoke-ChalkmateStep $python @('scripts/start_local_supabase.py') 'supabase-start'
if (!$apiRunning) { Invoke-ChalkmateStep $python @('scripts/local_setup.py') 'local-setup' }
Invoke-ChalkmateStep $python @('scripts/build_workers.py') 'workers-build'
Invoke-ChalkmateStep 'docker' @('compose','--env-file','.env','-f','infra/compose.yaml','--profile','workers','up','-d','--no-build') 'workers-start'
if (!$webRunning -and !$SkipBuild) { Invoke-ChalkmateStep 'npm.cmd' @('run','build') 'web-build' }
if (!$apiRunning) {
    $env:WEB_ORIGIN = $webAddress
    $apiArguments = @('-m','uvicorn','chalkmate.main:app','--app-dir',('"' + (Join-Path $ChalkmateRoot 'services\api\src') + '"'),'--host','127.0.0.1','--port','8100')
    $apiProcess = Start-Process -FilePath $python -ArgumentList $apiArguments -WorkingDirectory $ChalkmateRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ChalkmateRuntime 'api-output.log') -RedirectStandardError (Join-Path $ChalkmateRuntime 'api-error.log') -PassThru
    Save-ChalkmateProcess $apiProcess 'api' $apiAddress
}
if (!$webRunning) {
    $node = (Get-Command node).Source
    $next = Join-Path $ChalkmateRoot 'node_modules\next\dist\bin\next'
    $webArguments = @(('"' + $next + '"'),'start',('"' + (Join-Path $ChalkmateRoot 'apps\web') + '"'),'--hostname','127.0.0.1','--port',"$webPort")
    $webProcess = Start-Process -FilePath $node -ArgumentList $webArguments -WorkingDirectory $ChalkmateRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ChalkmateRuntime 'web-output.log') -RedirectStandardError (Join-Path $ChalkmateRuntime 'web-error.log') -PassThru
    Save-ChalkmateProcess $webProcess 'web' $webAddress
}
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ((Test-ChalkmateHealth $apiAddress 'chalkmate-api') -and (Test-ChalkmateHealth $webAddress 'chalkmate-web')) {
        Write-Output "Chalkmate ready: $webAddress"
        Write-Output 'Local email inbox: http://127.0.0.1:54324'
        Write-Output 'Stop managed app processes: .\scripts\Stop-Chalkmate.ps1'
        exit 0
    }
    Start-Sleep -Seconds 1
}
throw 'Application did not become healthy; inspect .tmp/local logs and run Stop-Chalkmate.ps1 before retrying'
