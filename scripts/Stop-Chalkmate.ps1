param([switch]$Services)
. (Join-Path $PSScriptRoot 'Local-Common.ps1')
Set-Location -LiteralPath $ChalkmateRoot
foreach ($name in @('web','api')) {
    $recordPath = Join-Path $ChalkmateRuntime "$name.json"
    if (!(Test-Path -LiteralPath $recordPath)) { continue }
    $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    $tracked = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$record.pid)"
    if ($tracked -and $tracked.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$record.created).ToUniversalTime().Ticks -and $tracked.CommandLine.Contains($ChalkmateRoot)) {
        # Windows venv python.exe can own a real Python child. Stop only children
        # belonging to this verified launcher process and this repository.
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$($tracked.ProcessId)" | Where-Object {
            $_.CommandLine -and $_.CommandLine.Contains($ChalkmateRoot) -and $_.CreationDate -ge $tracked.CreationDate
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $tracked.ProcessId -ErrorAction SilentlyContinue
        Write-Output "Stopped managed Chalkmate $name"
    } elseif ($tracked) {
        throw "Process identity changed for $name; no process was stopped"
    }
    Remove-Item -LiteralPath $recordPath
}
if ($Services) {
    New-Item -ItemType Directory -Path $ChalkmateRuntime -Force | Out-Null
    Invoke-ChalkmateStep 'docker' @('compose','--env-file','.env','-f','infra/compose.yaml','--profile','workers','down') 'workers-stop'
    # Supabase stop preserves database/file volumes; no reset or volume removal.
    Invoke-ChalkmateStep (Join-Path $ChalkmateRoot 'node_modules\.bin\supabase.cmd') @('stop') 'supabase-stop'
}
