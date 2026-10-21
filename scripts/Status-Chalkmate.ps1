. (Join-Path $PSScriptRoot 'Local-Common.ps1')
foreach ($entry in @(@('API','http://127.0.0.1:8100','chalkmate-api'),@('Web','http://localhost:3000','chalkmate-web'),@('Web','http://localhost:3001','chalkmate-web'))) {
    $ready = Test-ChalkmateHealth $entry[1] $entry[2]
    Write-Output "$($entry[0]) $($entry[1]): $(if ($ready) {'ready'} else {'not running here'})"
}
Write-Output 'Open classroom Readiness for sign-in, files, queue, worker and local AI checks.'
