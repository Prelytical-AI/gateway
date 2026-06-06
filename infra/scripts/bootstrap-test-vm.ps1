#Requires -Version 5.1
param(
    [Parameter(Mandatory = $true)]
    [string]$ReadOnlyPassword,

    [string]$DatabaseName = "PrelyticalDemoDW",
    [string]$ReadOnlyLogin = "prelytical_readonly",
    [string]$BootstrapDir = "C:\PrelyticalBootstrap",
    [string]$SeedSqlPath = "C:\PrelyticalBootstrap\05_seed_test_warehouse.sql"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $BootstrapDir | Out-Null
$logPath = Join-Path $BootstrapDir "bootstrap.log"

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logPath -Value $line
    Write-Host $line
}

function Get-SqlCmdPath {
    $candidate = Get-ChildItem -Path "C:\Program Files\Microsoft SQL Server" -Filter sqlcmd.exe -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if (-not $candidate) {
        throw "sqlcmd.exe not found."
    }
    return $candidate.FullName
}

function Enable-SqlMixedMode {
    $instanceKey = Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL" |
        Get-ItemProperty |
        Select-Object -ExpandProperty MSSQLSERVER

    $serverKey = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\$instanceKey\MSSQLServer"
    Set-ItemProperty -Path $serverKey -Name LoginMode -Value 2
    Write-Log "Enabled SQL mixed mode authentication."

    $tcpKey = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\$instanceKey\MSSQLServer\SuperSocketNetLib\Tcp\IPAll"
    if (Test-Path $tcpKey) {
        Set-ItemProperty -Path $tcpKey -Name TcpPort -Value "1433"
        Set-ItemProperty -Path $tcpKey -Name TcpDynamicPorts -Value ""
    }

    $enabledKey = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\$instanceKey\MSSQLServer\SuperSocketNetLib\Tcp"
    if (Test-Path $enabledKey) {
        Set-ItemProperty -Path $enabledKey -Name Enabled -Value 1
    }

    Restart-Service MSSQLSERVER -Force
    Start-Sleep -Seconds 10
    Write-Log "Restarted SQL Server and configured TCP 1433."
}

function Invoke-Sql {
    param([string]$Query)
    & $sqlcmd -S localhost -E -b -Q $Query
    if ($LASTEXITCODE -ne 0) {
        throw "SQL failed: $Query"
    }
}

Write-Log "Starting Prelytical gateway test VM bootstrap."

$service = Get-Service -Name MSSQLSERVER -ErrorAction SilentlyContinue
if (-not $service) {
    throw "MSSQLSERVER service not found."
}

for ($i = 0; $i -lt 30; $i++) {
    if ((Get-Service MSSQLSERVER).Status -eq "Running") { break }
    Start-Sleep -Seconds 10
}
if ((Get-Service MSSQLSERVER).Status -ne "Running") {
    throw "SQL Server did not start."
}

Enable-SqlMixedMode
$sqlcmd = Get-SqlCmdPath

if (-not (Test-Path $SeedSqlPath)) {
    throw "Seed SQL file not found at $SeedSqlPath"
}

Write-Log "Running seed SQL from $SeedSqlPath"
& $sqlcmd -S localhost -E -b -i $SeedSqlPath
if ($LASTEXITCODE -ne 0) {
    throw "Seed SQL failed."
}

$escapedPassword = $ReadOnlyPassword.Replace("'", "''")
Invoke-Sql "IF NOT EXISTS (SELECT * FROM sys.sql_logins WHERE name = N'$ReadOnlyLogin') CREATE LOGIN [$ReadOnlyLogin] WITH PASSWORD = N'$escapedPassword';"
Invoke-Sql "USE [$DatabaseName]; IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = N'$ReadOnlyLogin') CREATE USER [$ReadOnlyLogin] FOR LOGIN [$ReadOnlyLogin];"
Invoke-Sql "USE [$DatabaseName]; GRANT SELECT ON SCHEMA::dbo TO [$ReadOnlyLogin]; GRANT SELECT ON SCHEMA::ai TO [$ReadOnlyLogin];"
Invoke-Sql "USE [$DatabaseName]; DENY INSERT, UPDATE, DELETE, ALTER, CONTROL TO [$ReadOnlyLogin];"

Write-Log "Configured read-only login $ReadOnlyLogin on database $DatabaseName."

if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Log "Installing Chocolatey."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString("https://community.chocolatey.org/install.ps1"))
}

Write-Log "Installing Git."
choco install git -y --no-progress | Out-Null

$readme = @"
Prelytical Gateway Test VM
==========================

Database: $DatabaseName
Host: localhost
Port: 1433
Read-only login: $ReadOnlyLogin
Read-only password: $ReadOnlyPassword

Tables: dbo.Regions, dbo.ProductCategories, dbo.Customers, dbo.Orders
Views: ai.vw_sales_by_region, ai.vw_sales_by_category, ai.vw_monthly_revenue

Next steps:
1. RDP to this instance
2. git clone https://github.com/Prelytical-AI/gateway.git C:\Projects\gateway
3. Follow README.md for fresh install
"@

Set-Content -Path (Join-Path $BootstrapDir "README.txt") -Value $readme -Encoding UTF8
Set-Content -Path (Join-Path $BootstrapDir "complete.txt") -Value (Get-Date -Format o) -Encoding UTF8
Write-Log "Bootstrap complete."
