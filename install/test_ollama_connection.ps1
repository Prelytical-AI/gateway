#Requires -Version 5.1
param()

Write-Host "=== Test Ollama connection ===" -ForegroundColor Cyan

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
$baseUrl = "http://localhost:11434/v1"
$modelName = "qwen2.5-coder:7b"

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^MODEL_BASE_URL=(.+)$') { $baseUrl = $Matches[1].Trim() }
        if ($_ -match '^MODEL_NAME=(.+)$') { $modelName = $Matches[1].Trim() }
    }
}

$uri = "$($baseUrl.TrimEnd('/'))/chat/completions"
$body = @{
    model = $modelName
    messages = @(
        @{ role = "system"; content = "You are a helpful assistant." }
        @{ role = "user"; content = "Return the word ok." }
    )
    temperature = 0
} | ConvertTo-Json -Depth 5

try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120
    $content = $response.choices[0].message.content
    Write-Host "Model response: $content" -ForegroundColor Green
} catch {
    Write-Host "Ollama test failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Ensure Ollama is running and model '$modelName' is pulled."
    exit 1
}
