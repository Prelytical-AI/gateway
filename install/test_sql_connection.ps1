#Requires -Version 5.1
param()

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "=== Test SQL Server connection ===" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Write-Host "Missing .env. Run configure_env_wizard.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\pip.exe install -r requirements.txt
}

$code = @'
from app.services.sqlserver import SQLServerService
service = SQLServerService()
ok, message = service.test_connection()
print("ok=" + str(ok))
print(message)
if not ok:
    raise SystemExit(1)
'@

.\.venv\Scripts\python.exe -c $code
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
