# Starts Vikas Vaani locally: citizen portal at http://127.0.0.1:8000/ and government dashboard at /admin.
#
#   .\start.ps1            set up what is missing, then start the server and open the browser
#   .\start.ps1 -Reset     also reload the synthetic demo complaints (wipes complaints filed locally)
#
# First run: creates .venv, installs the backend, builds indicators and synthetic data if missing, seeds the local
# store. Later runs start in a few seconds. Stop the server with Ctrl+C.
param([switch]$Reset, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

function Test-Venv {
    if (-not (Test-Path $py)) { return $false }
    try { & $py -c "import fastapi, h3, uvicorn" 2>$null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

if (-not (Test-Venv)) {
    Write-Host 'Setting up the Python environment in .venv (first run, takes a minute)...' -ForegroundColor Cyan
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv --clear .venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv --clear .venv }
    else { throw 'Python 3.11+ was not found. Install it from https://www.python.org/downloads/ and run this again.' }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv' }
    & $py -m pip install --disable-pip-version-check -q -r backend\requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the backend requirements' }
}

Push-Location backend
try {
    if (-not (Test-Path ..\data\processed\IN\indicators.csv)) {
        Write-Host 'Building indicator tables...' -ForegroundColor Cyan
        & $py -m scripts.build_indicators --pack all --allow-placeholder | Out-Null
    }
    if (-not (Test-Path ..\data\synthetic\IN\requests.jsonl)) {
        Write-Host 'Generating synthetic demo complaints...' -ForegroundColor Cyan
        & $py -m scripts.generate_synthetic --pack all
    }
    if ($Reset -or -not (Test-Path ..\data\store\IN\requests.jsonl)) {
        Write-Host 'Loading demo complaints into the local store...' -ForegroundColor Cyan
        $env:REPOSITORY = 'local'
        & $py -m scripts.seed --reset
    }

    $url = "http://127.0.0.1:$Port/"
    Write-Host ''
    Write-Host "Citizen portal:        $url" -ForegroundColor Green
    Write-Host "Government dashboard:  ${url}admin" -ForegroundColor Green
    Write-Host "API docs:              ${url}docs" -ForegroundColor Green
    Write-Host 'Press Ctrl+C to stop.'
    Write-Host ''
    Start-Job -ScriptBlock { param($u) Start-Sleep -Seconds 3; Start-Process $u } -ArgumentList $url | Out-Null
    $env:REPOSITORY = 'local'
    & $py -m uvicorn app.main:app --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}
