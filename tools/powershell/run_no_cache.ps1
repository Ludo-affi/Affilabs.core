# PYTHONDONTWRITEBYTECODE prevents .pyc file creation
$env:PYTHONDONTWRITEBYTECODE = "1"

# Clear any existing cache before starting
Write-Host "Clearing Python cache..." -ForegroundColor Yellow
Get-ChildItem -Path "src" -Include __pycache__ -Recurse -Force -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path "src" -Include *.pyc,*.pyo,*.pyd -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host "Starting application with NO CACHE MODE..." -ForegroundColor Green
Write-Host ""

# Change to src and run
Push-Location -Path "src"
python -B main_simplified.py
Pop-Location

# Clear environment variable
$env:PYTHONDONTWRITEBYTECODE = $null
