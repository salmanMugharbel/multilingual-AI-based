# Starts the whole system locally:
#   1. Ollama (local LLM server)      http://127.0.0.1:11434
#   2. FastAPI backend + built React  http://127.0.0.1:8000
#
#   .\start.ps1                 -> uses qwen2.5:3b   (better answers, needs ~3 GB free RAM)
#   .\start.ps1 -Llm qwen2.5:1.5b -> smaller/faster model for low-memory situations
#
# TIP (8 GB laptop): close the browser tabs you don't need, Oracle DB, VS Code and Telegram
# before the demo. When RAM is full, Windows pages the model to disk and answers become very slow.
# For frontend development with hot reload run instead:  cd frontend; npm run dev  (port 5173)
param([string]$Llm = "qwen2.5:3b")

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = "$env:USERPROFILE\.venvs\rk2\Scripts\python.exe"
$ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"

if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Starting Ollama..."
    Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

if (-not (Test-Path "$root\frontend\dist")) {
    Write-Host "Building frontend..."
    Push-Location "$root\frontend"; npm install; npm run build; Pop-Location
}

$os = Get-CimInstance Win32_OperatingSystem
$free = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
Write-Host "Free RAM: $free GB   LLM: $Llm"
if ($free -lt 3) { Write-Host "WARNING: less than 3 GB RAM free - close other programs for fast answers." -ForegroundColor Yellow }

$env:DOCQA_LLM = $Llm
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_OFFLINE = "1"          # all models are already downloaded; work fully offline
Write-Host "Open http://127.0.0.1:8000 in your browser"
Set-Location "$root\backend"
$ErrorActionPreference = "Continue"   # uvicorn logs to stderr; that is not an error
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
