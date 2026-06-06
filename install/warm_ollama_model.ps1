#Requires -Version 5.1
param()

Write-Host "=== Warm up Ollama model ===" -ForegroundColor Cyan

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama is not installed. Run install_ollama_windows.ps1 first." -ForegroundColor Red
    exit 1
}

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
$modelName = "qwen2.5-coder:7b"

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^MODEL_NAME=(.+)$') { $modelName = $Matches[1].Trim() }
    }
}

Write-Host "Model: $modelName"
Write-Host "Loading model into memory (first run can take several minutes on CPU)..." -ForegroundColor Yellow

$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $output = ollama run $modelName "Return the word ok." 2>&1
    $sw.Stop()
    Write-Host "Warmup complete in $([math]::Round($sw.Elapsed.TotalSeconds))s" -ForegroundColor Green
    Write-Host "Response: $output"
} catch {
    Write-Host "Warmup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Model is loaded. Ask questions in the UI should be faster now." -ForegroundColor Cyan
