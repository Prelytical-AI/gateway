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

$baseUrl = $baseUrl.TrimEnd('/')
$isRemote = $baseUrl -notmatch '^https?://(localhost|127\.0\.0\.1)(:|/|$)'

Write-Host "Model base URL: $baseUrl" -ForegroundColor DarkGray
Write-Host "Model name:       $modelName" -ForegroundColor DarkGray
if ($isRemote) {
    Write-Host "Mode:             remote GPU inference VM (Option 2)" -ForegroundColor DarkGray
}

# Ollama OpenAI-compatible base is .../v1; native tags API is on the host root.
$rootHost = $baseUrl -replace '/v1/?$', ''
$tagsUri = "$rootHost/api/tags"

Write-Host ""
Write-Host "Checking Ollama tags endpoint: $tagsUri" -ForegroundColor Yellow
try {
    $tags = Invoke-RestMethod -Uri $tagsUri -Method Get -TimeoutSec 15
    $tagNames = @($tags.models | ForEach-Object { $_.name })
    if ($tagNames.Count -gt 0) {
        Write-Host "Available models: $($tagNames -join ', ')" -ForegroundColor Green
    } else {
        Write-Host "Ollama reachable but no models listed yet." -ForegroundColor Yellow
    }
    if ($tagNames -notcontains $modelName -and ($tagNames | Where-Object { $_ -like "$modelName*" }).Count -eq 0) {
        Write-Host "WARN: '$modelName' not found on server. Run ollama pull on the inference VM." -ForegroundColor Yellow
    }
} catch {
    Write-Host "Tags check failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($isRemote) {
        Write-Host ""
        Write-Host "Remote Ollama troubleshooting:" -ForegroundColor Yellow
        Write-Host "  - Confirm GPU VM private IP in MODEL_BASE_URL (.env)"
        Write-Host "  - Firewall/SG: allow TCP 11434 from this SQL VM to the GPU VM"
        Write-Host "  - On GPU VM: sudo systemctl status ollama"
        Write-Host "  - See docs/GPU_INFERENCE_VM.md"
    } else {
        Write-Host "Ensure Ollama is running locally (install_ollama_windows.ps1)."
    }
    exit 1
}

$uri = "$baseUrl/chat/completions"
$body = @{
    model = $modelName
    messages = @(
        @{ role = "system"; content = "You are a helpful assistant." }
        @{ role = "user"; content = "Return the word ok." }
    )
    temperature = 0
} | ConvertTo-Json -Depth 5

Write-Host ""
Write-Host "Sending test chat request..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120
    $content = $response.choices[0].message.content
    Write-Host "Model response: $content" -ForegroundColor Green
    Write-Host ""
    Write-Host "Ollama connection OK." -ForegroundColor Green
} catch {
    Write-Host "Chat test failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Ensure model '$modelName' is pulled on the Ollama host."
    exit 1
}
