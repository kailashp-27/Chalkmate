$ErrorActionPreference = 'Stop'
$ChalkmateRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ChalkmateRuntime = Join-Path $ChalkmateRoot '.tmp\local'

function Test-ChalkmateHealth([string]$Address, [string]$Service) {
    try {
        $health = Invoke-RestMethod -Uri "$Address/health" -TimeoutSec 3
        return $health.status -eq 'ok' -and $health.service -eq $Service
    } catch { return $false }
}

function Save-ChalkmateProcess($Process, [string]$Name, [string]$Address) {
    $identity = Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
    if (!$identity) { throw "$Name exited during startup; see .tmp/local logs" }
    @{
        pid = $Process.Id
        created = $identity.CreationDate.ToUniversalTime().ToString('o')
        name = $Name
        address = $Address
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ChalkmateRuntime "$Name.json")
}

function Invoke-ChalkmateStep([string]$Program, [string[]]$Arguments, [string]$Name) {
    Write-Output $Name
    # Commands can produce generated keys; keep output in ignored local files.
    & $Program @Arguments *> (Join-Path $ChalkmateRuntime "$Name.log")
    if ($LASTEXITCODE -ne 0) { throw "$Name failed; inspect .tmp/local/$Name.log privately" }
}
