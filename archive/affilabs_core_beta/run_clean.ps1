# Start the application with clean cache
# This script clears cache and runs the application

Write-Host "Starting ezControl with clean cache..." -ForegroundColor Cyan
Write-Host ""

# Clear cache
& "$PSScriptRoot\clear_cache.ps1"

# Run application with -B flag (don't write bytecode)
python -B main_simplified.py
