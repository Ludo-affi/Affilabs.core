# Clear Python bytecode cache to ensure fresh module loads
# Run this before starting the application if you've made code changes

Write-Host "Clearing Python cache..." -ForegroundColor Yellow

# Remove all __pycache__ directories recursively
Get-ChildItem -Path . -Include __pycache__ -Recurse -Force -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Remove all .pyc files
Get-ChildItem -Path . -Include *.pyc -Recurse -Force | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "✓ Cache cleared!" -ForegroundColor Green
Write-Host ""
Write-Host "Now run: python -B main_simplified.py" -ForegroundColor Cyan
