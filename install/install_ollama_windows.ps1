#Requires -Version 5.1
param(
    [switch]$SkipConfirm
)

Write-Host "=== Install Ollama for Windows ===" -ForegroundColor Cyan

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Ollama already installed:" (ollama --version)
    exit 0
}

Write-Host ""
Write-Host "This script can install Ollama using the official installer command:"
Write-Host "  irm https://ollama.com/install.ps1 | iex"
Write-Host ""
Write-Host "Manual download: https://ollama.com/download/windows"
Write-Host ""

if (-not $SkipConfirm) {
    $answer = Read-Host "Proceed with official Ollama install script? (y/N)"
    if ($answer -notin @("y", "Y", "yes", "Yes")) {
        Write-Host "Skipped automatic install. Install Ollama manually, then rerun pull_default_models.ps1"
        exit 0
    }
}

try {
    Invoke-Expression "& { $(Invoke-RestMethod -Uri 'https://ollama.com/install.ps1') }"
} catch {
    Write-Host "Automatic install failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Install manually from https://ollama.com/download/windows"
    exit 1
}

Start-Sleep -Seconds 3
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Ollama installed:" (ollama --version) -ForegroundColor Green
} else {
    Write-Host "Ollama command not found after install. Restart PowerShell or log out/in." -ForegroundColor Yellow
}
