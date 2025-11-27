# Python Cache Prevention - Add to user environment
# Run this ONCE to set permanent environment variable

Write-Host "Setting permanent Python cache prevention..." -ForegroundColor Cyan
Write-Host ""

# Set user-level environment variable
[System.Environment]::SetEnvironmentVariable(
    "PYTHONDONTWRITEBYTECODE",
    "1",
    [System.EnvironmentVariableTarget]::User
)

Write-Host "✓ Set PYTHONDONTWRITEBYTECODE=1 for your user account" -ForegroundColor Green
Write-Host ""
Write-Host "This will prevent Python from creating .pyc files system-wide" -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️  Note: This applies to ALL Python applications you run" -ForegroundColor Yellow
Write-Host "If you want to revert, run: [Environment]::SetEnvironmentVariable('PYTHONDONTWRITEBYTECODE', `$null, 'User')" -ForegroundColor Gray
Write-Host ""
Write-Host "Close and reopen PowerShell for this to take effect." -ForegroundColor Cyan
