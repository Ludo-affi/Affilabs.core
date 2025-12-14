# ezControl Application Launcher
# Clears cache and runs application from new src/ structure

Write-Host "ezControl Application Launcher" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check for running Python processes
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ezControl*" -or $_.Path -like "*venv312*" }
if ($pythonProcesses) {
    Write-Host "WARNING: Found running Python process(es):" -ForegroundColor Yellow
    $pythonProcesses | ForEach-Object { Write-Host "   PID: $($_.Id) - Started: $($_.StartTime)" -ForegroundColor Gray }
    Write-Host ""
    $response = Read-Host "Kill these processes? (y/n)"
    if ($response -eq 'y' -or $response -eq 'Y') {
        $pythonProcesses | Stop-Process -Force
        Write-Host "   Processes terminated" -ForegroundColor Green
        Start-Sleep -Seconds 1
    }
    Write-Host ""
}

# Clear Python cache
Write-Host "[1/4] Clearing Python cache..." -ForegroundColor Yellow
$cacheCount = 0
$cacheCount += (Get-ChildItem -Path "src" -Include __pycache__ -Recurse -Force -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -PassThru).Count
$cacheCount += (Get-ChildItem -Path "src" -Include *.pyc,*.pyo -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force -PassThru).Count
if ($cacheCount -gt 0) {
    Write-Host "      Removed $cacheCount cache items" -ForegroundColor Green
} else {
    Write-Host "      No cache found (already clean)" -ForegroundColor Green
}
Write-Host ""

# Set environment variable for this session
Write-Host "[2/4] Setting no-cache mode for this session..." -ForegroundColor Yellow
$env:PYTHONDONTWRITEBYTECODE = "1"
Write-Host "      PYTHONDONTWRITEBYTECODE=1" -ForegroundColor Green
Write-Host ""

# Change to src directory
Write-Host "[3/4] Navigating to application directory..." -ForegroundColor Yellow
Push-Location -Path "src"
Write-Host "      Working directory: $(Get-Location)" -ForegroundColor Green
Write-Host ""

# Run application
Write-Host "[4/4] Starting ezControl..." -ForegroundColor Yellow
Write-Host "      Command: python -B main_simplified.py" -ForegroundColor Gray
Write-Host "      -B flag: Do not write .pyc files" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

python -B main_simplified.py

# Cleanup
Pop-Location
$env:PYTHONDONTWRITEBYTECODE = $null

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Application closed" -ForegroundColor Yellow
Write-Host ""
Write-Host "Cache was cleared and no new cache was created." -ForegroundColor Green
