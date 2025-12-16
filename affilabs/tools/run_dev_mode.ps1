# Launch ezControl in Developer Mode
# This enables additional configuration prompts and debugging features

Write-Host "Starting ezControl in Developer Mode..." -ForegroundColor Cyan
Write-Host ""

# Set dev mode environment variable
$env:AFFILABS_DEV = "1"

# Activate virtual environment and run
& "$PSScriptRoot\..\.venv312\Scripts\Activate.ps1"
python "$PSScriptRoot\main_simplified.py"

Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
