#Requires -Version 5.1
param(
    [string]$ServiceName = "PrelyticalSecureSqlGateway"
)

Write-Host "=== Uninstall Prelytical Windows service ===" -ForegroundColor Cyan

$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "NSSM not found. Nothing to uninstall via NSSM." -ForegroundColor Yellow
    exit 0
}

& nssm stop $ServiceName
& nssm remove $ServiceName confirm
Write-Host "Service '$ServiceName' removed." -ForegroundColor Green
