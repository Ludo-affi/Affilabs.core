# Quick launcher - ALWAYS uses Python 3.12 from .venv312
# Usage: .\run.ps1

$ErrorActionPreference = "Stop"

# Set UTF-8 encoding to prevent emoji crashes
$env:PYTHONIOENCODING = "utf-8"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check for .venv312
$PythonExe = Join-Path $ScriptDir ".venv312\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Python 3.12 venv not found at .venv312" -ForegroundColor Red
    Write-Host "Run: py -3.12 -m venv .venv312" -ForegroundColor Yellow
    exit 1
}

# Kill any stale Python processes
Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
    $_.Path -like "*venv312*" -or $_.Path -like "*Affilabs*" 
} | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Milliseconds 500

# Run main.py with Python 3.12
Write-Host "Starting with Python 3.12..." -ForegroundColor Cyan
& $PythonExe "main.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Exit code: $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
