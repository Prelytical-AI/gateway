#Requires -Version 5.1
param()

Write-Host "=== Prelytical .env configuration wizard ===" -ForegroundColor Cyan

$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root ".env"
$examplePath = Join-Path $root ".env.example"

if (-not (Test-Path $examplePath)) {
    Write-Host "Missing .env.example at $examplePath" -ForegroundColor Red
    exit 1
}

function Read-Default {
    param([string]$Prompt, [string]$Default)
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}

$sqlHost = Read-Default "SQL Server host" "localhost"
$sqlInstance = Read-Host "SQL Server instance (press Enter for default instance - NOT the database name)"
$sqlDatabase = Read-Default "SQL Server database" "PrelyticalDemoDW"
$sqlUser = Read-Default "SQL username" "prelytical_readonly"
$sqlPassword = Read-Host "SQL password" -AsSecureString
$sqlPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sqlPassword)
)
$odbcDriver = Read-Default "ODBC driver (17 or 18 for SQL Server)" "ODBC Driver 18 for SQL Server"

Write-Host ""
Write-Host "Where does Ollama run?" -ForegroundColor Cyan
Write-Host "  1) This SQL/gateway VM (localhost - same-VM / Option 1)"
Write-Host "  2) Separate GPU VM on the private network (Option 2)"
Write-Host ""
$ollamaChoice = Read-Host "Choice [1]"
if ($ollamaChoice -eq "2") {
    $gpuIp = Read-Host "GPU VM private IP (e.g. 10.0.2.47)"
    $gpuIp = $gpuIp.Trim()
    if ([string]::IsNullOrWhiteSpace($gpuIp)) {
        Write-Host "No IP entered; falling back to localhost." -ForegroundColor Yellow
        $modelBaseUrl = "http://localhost:11434/v1"
    } else {
        $modelBaseUrl = "http://${gpuIp}:11434/v1"
        Write-Host ""
        Write-Host "Remote Ollama: $modelBaseUrl" -ForegroundColor Green
        Write-Host "On this SQL VM, skip install_ollama_windows.ps1 and pull_default_models.ps1." -ForegroundColor DarkGray
        Write-Host "Bootstrap the GPU VM with install/bootstrap-inference-linux.sh (see docs/GPU_INFERENCE_VM.md)." -ForegroundColor DarkGray
    }
} else {
    $modelBaseUrl = Read-Default "Model base URL" "http://localhost:11434/v1"
}
$modelName = Read-Default "Model name" "qwen2.5-coder:7b"
$appPort = Read-Default "App port" "8080"

$content = Get-Content $examplePath -Raw
$content = $content -replace '(?m)^SQLSERVER_HOST=.*$', "SQLSERVER_HOST=$sqlHost"
$content = $content -replace '(?m)^SQLSERVER_INSTANCE=.*$', "SQLSERVER_INSTANCE=$sqlInstance"
$content = $content -replace '(?m)^SQLSERVER_DATABASE=.*$', "SQLSERVER_DATABASE=$sqlDatabase"
$content = $content -replace '(?m)^SQLSERVER_USERNAME=.*$', "SQLSERVER_USERNAME=$sqlUser"
$content = $content -replace '(?m)^SQLSERVER_PASSWORD=.*$', "SQLSERVER_PASSWORD=$sqlPasswordPlain"
$content = $content -replace '(?m)^SQLSERVER_DRIVER=.*$', "SQLSERVER_DRIVER=$odbcDriver"
$content = $content -replace '(?m)^MODEL_BASE_URL=.*$', "MODEL_BASE_URL=$modelBaseUrl"
$content = $content -replace '(?m)^MODEL_NAME=.*$', "MODEL_NAME=$modelName"
$content = $content -replace '(?m)^APP_PORT=.*$', "APP_PORT=$appPort"

Set-Content -Path $envPath -Value $content -Encoding UTF8

Write-Host ""
Write-Host ".env written to $envPath" -ForegroundColor Green
Write-Host "SQL password was masked in console output." -ForegroundColor DarkGray
