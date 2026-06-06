#Requires -Version 5.1
param()

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "=== Start Prelytical Secure SQL Gateway ===" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Write-Host "Missing .env. Run configure_env_wizard.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt

Write-Host ""
Write-Host "Starting app at http://127.0.0.1:8080" -ForegroundColor Green
.\.venv\Scripts\python.exe run_local.py
