# ============================================================================
# ROBUST PYTHON 3.12 LAUNCHER (PowerShell)
# This script FORCES the use of Python 3.12 virtual environment
# ============================================================================

Write-Host ""
Write-Host "========================================"
Write-Host "  SPR Control App - Python 3.12 ONLY"
Write-Host "========================================"
Write-Host ""

# Get the directory where this script is located
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

# Check if .venv312 exists
$PythonExe = Join-Path $AppDir ".venv312\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Python 3.12 virtual environment not found!" -ForegroundColor Red
    Write-Host "Expected location: $AppDir\.venv312" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create the virtual environment first:" -ForegroundColor Yellow
    Write-Host "   py -3.12 -m venv .venv312" -ForegroundColor Yellow
    Write-Host "   .\.venv312\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Verify Python version
Write-Host "Verifying Python 3.12..." -ForegroundColor Cyan
$version = & $PythonExe --version 2>&1
Write-Host $version -ForegroundColor Green

if ($version -notmatch "Python 3\.12") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  ⚠️  WARNING: NOT PYTHON 3.12!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Expected: Python 3.12.x" -ForegroundColor Yellow
    Write-Host "Got: $version" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This may cause errors. Press Ctrl+C to abort." -ForegroundColor Yellow
    Write-Host "Or press Enter to continue anyway..." -ForegroundColor Yellow
    Read-Host
}

# Set PYTHONPATH to workspace root
$env:PYTHONPATH = $AppDir

Write-Host ""
Write-Host "Using Python: $PythonExe" -ForegroundColor Green
Write-Host "PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Green
Write-Host ""
Write-Host "Starting application..." -ForegroundColor Cyan
Write-Host ""

# Run the application using the SPECIFIC Python 3.12 executable
& $PythonExe "main\main.py"

# Check exit code
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "========================================"
    Write-Host "  Application exited with error code: $LASTEXITCODE"
    Write-Host "========================================"
    Read-Host "Press Enter to exit"
}
