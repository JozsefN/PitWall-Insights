param([int]$Port = 8000, [switch]$NoReload)
$ErrorActionPreference = 'Stop'
$backendDirectory = (Resolve-Path (Join-Path $PSScriptRoot '..\backend')).Path
$backendPython = Join-Path $backendDirectory '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $backendPython)) {
    throw 'Backend virtual environment is missing. Create backend\.venv and install backend requirements first.'
}
$workerLogDirectory = Join-Path $env:TEMP 'pitwall-worker'
New-Item -ItemType Directory -Path $workerLogDirectory -Force | Out-Null
$workerProcess = $null
Push-Location $backendDirectory
try {
    docker compose up -d --wait
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL could not be started.' }
    & $backendPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migrations failed.' }
    $existingWorkers = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'python.exe' -and $_.CommandLine -match '-m\s+app\.worker' -and
            $_.CommandLine.Contains($backendPython)
    }
    if (-not $existingWorkers) {
        $workerProcess = Start-Process -FilePath $backendPython -ArgumentList '-u','-m','app.worker' `
            -WorkingDirectory $backendDirectory -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $workerLogDirectory 'stdout.log') `
            -RedirectStandardError (Join-Path $workerLogDirectory 'stderr.log')
    }
    Write-Host "Starting API with telemetry worker. New worker logs: $workerLogDirectory"
    $apiArguments = @('-m', 'uvicorn', 'app.main:app', '--port', "$Port")
    if (-not $NoReload) { $apiArguments += '--reload' }
    & $backendPython @apiArguments
} finally {
    # Stop only the worker owned by this invocation, including the venv shim child.
    if ($workerProcess -and -not $workerProcess.HasExited) {
        Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $workerProcess.Id } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $workerProcess.Id -ErrorAction SilentlyContinue
    }
    Pop-Location
}
