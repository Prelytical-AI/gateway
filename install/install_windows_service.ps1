#Requires -Version 5.1
param(
    [string]$ServiceName = "PrelyticalSecureSqlGateway"
)

Write-Host "=== Optional Windows service install ===" -ForegroundColor Cyan

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$runScript = Join-Path $root "run_local.py"

if (-not (Test-Path $pythonExe)) {
    Write-Host "Virtual environment not found. Run start_prelytical.ps1 once first." -ForegroundColor Red
    exit 1
}

$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "NSSM not found. Service install is optional for today's POC." -ForegroundColor Yellow
    Write-Host "For now, use: .\install\start_prelytical.ps1"
    Write-Host "To install as a service later, install NSSM and rerun this script."
    exit 0
}

& nssm install $ServiceName $pythonExe $runScript
& nssm set $ServiceName AppDirectory $root
& nssm set $ServiceName DisplayName "Prelytical Secure SQL Gateway"
& nssm set $ServiceName Description "Same-VM SQL Server + Ollama POC"
& nssm start $ServiceName

Write-Host "Service '$ServiceName' installed and started." -ForegroundColor Green
