#Requires -Version 5.1
param()

Write-Host "=== Prelytical VM Readiness Check ===" -ForegroundColor Cyan

function Test-ItemSoft {
    param(
        [string]$Label,
        [scriptblock]$Check,
        [string]$PassHint = "",
        [string]$FailHint = ""
    )
    Write-Host ""
    Write-Host $Label -ForegroundColor Yellow
    try {
        $result = & $Check
        if ($result) {
            Write-Host "  OK: $PassHint" -ForegroundColor Green
        } else {
            Write-Host "  WARN: $FailHint" -ForegroundColor DarkYellow
        }
    } catch {
        Write-Host "  WARN: $($_.Exception.Message)" -ForegroundColor DarkYellow
        if ($FailHint) { Write-Host "  Hint: $FailHint" -ForegroundColor DarkGray }
    }
}

Write-Host "Windows version:" (Get-CimInstance Win32_OperatingSystem).Caption
Write-Host "Current user:" (whoami)

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
Write-Host "Admin rights:" $(if ($isAdmin) { "Yes" } else { "No (some install steps may require elevation)" })

Write-Host "PowerShell version:" $PSVersionTable.PSVersion

Test-ItemSoft "Python installed?" { Get-Command python -ErrorAction SilentlyContinue } "python found" "Install Python 3.11+ from python.org"
Test-ItemSoft "pip installed?" { python -m pip --version 2>$null } "pip available" "Run: python -m pip install --upgrade pip"
Test-ItemSoft "Git installed?" { Get-Command git -ErrorAction SilentlyContinue } "git found" "Optional but recommended"

Write-Host ""
Write-Host "SQL Server services:" -ForegroundColor Yellow
Get-Service | Where-Object { $_.Name -like "*SQL*" -or $_.DisplayName -like "*SQL*" } |
    Select-Object Status, Name, DisplayName |
    Format-Table -AutoSize

Write-Host "ODBC drivers for SQL Server:" -ForegroundColor Yellow
Get-OdbcDriver | Where-Object { $_.Name -like "*SQL Server*" } | Select-Object Name | Format-Table -AutoSize

Write-Host "Network checks:" -ForegroundColor Yellow
foreach ($target in @(
    @{ Name = "ollama.com:443"; Host = "ollama.com"; Port = 443 },
    @{ Name = "localhost Ollama:11434"; Host = "localhost"; Port = 11434 },
    @{ Name = "localhost Prelytical:8080"; Host = "localhost"; Port = 8080 }
)) {
    try {
        $test = Test-NetConnection -ComputerName $target.Host -Port $target.Port -WarningAction SilentlyContinue
        if ($test.TcpTestSucceeded) {
            Write-Host "  OK: $($target.Name)" -ForegroundColor Green
        } else {
            Write-Host "  WARN: $($target.Name) not reachable" -ForegroundColor DarkYellow
        }
    } catch {
        Write-Host "  WARN: $($target.Name) check failed" -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "Readiness check complete. Review warnings above before continuing." -ForegroundColor Cyan
