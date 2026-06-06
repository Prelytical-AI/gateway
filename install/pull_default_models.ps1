#Requires -Version 5.1
param()

Write-Host "=== Pull default Ollama models ===" -ForegroundColor Cyan

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama is not installed. Run install_ollama_windows.ps1 first." -ForegroundColor Red
    exit 1
}

$models = @(
    "qwen2.5-coder:7b",
    "llama3.1:8b"
)

foreach ($model in $models) {
    Write-Host ""
    Write-Host "Pulling $model ..." -ForegroundColor Yellow
    try {
        ollama pull $model
        Write-Host "  OK: $model" -ForegroundColor Green
    } catch {
        Write-Host "  WARN: failed to pull $model - $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "Model pull step complete." -ForegroundColor Cyan
