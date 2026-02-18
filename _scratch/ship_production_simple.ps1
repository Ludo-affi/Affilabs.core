# Affilabs-Core Production Shipping Script
# Simple build script without Unicode characters

param(
    [string]$Version = "1.0.0-beta",
    [string]$Target = "exe",  # Options: exe, source, all
    [switch]$SkipTests = $false,
    [switch]$Clean = $false
)

$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "AFFILABS-CORE PRODUCTION SHIPPING" -ForegroundColor Cyan
Write-Host "Version: $Version" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$WorkspaceRoot = $PSScriptRoot
$DistDir = Join-Path $WorkspaceRoot "dist"

# Step 1: Clean if requested
if ($Clean) {
    Write-Host "[1/5] Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path $DistDir) {
        Remove-Item -Recurse -Force $DistDir
        Write-Host "  [OK] Cleaned dist/" -ForegroundColor Green
    }
    if (Test-Path "build") {
        Remove-Item -Recurse -Force "build"
        Write-Host "  [OK] Cleaned build/" -ForegroundColor Green
    }
} else {
    Write-Host "[1/5] Skipping clean (use -Clean to clean)" -ForegroundColor Gray
}

# Step 2: Activate virtual environment
Write-Host "[2/5] Activating virtual environment..." -ForegroundColor Yellow
$VenvActivate = Join-Path $WorkspaceRoot ".venv312\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    & $VenvActivate
    Write-Host "  [OK] Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Virtual environment not found: $VenvActivate" -ForegroundColor Red
    exit 1
}

# Step 3: Verify Python version
Write-Host "[3/5] Verifying Python version..." -ForegroundColor Yellow
$PythonVersion = python --version 2>&1
if ($PythonVersion -match "Python 3\.12") {
    Write-Host "  [OK] $PythonVersion" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Python 3.12+ required, found: $PythonVersion" -ForegroundColor Red
    exit 1
}

# Step 4: Create output directory
Write-Host "[4/5] Creating output directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
Write-Host "  [OK] Created: $DistDir" -ForegroundColor Green

# Step 5: Build executable
Write-Host "[5/5] Building standalone executable..." -ForegroundColor Yellow

# Check if PyInstaller is installed
$HasPyInstaller = python -c "import PyInstaller" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [INFO] Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Build executable
Write-Host "  [INFO] Running PyInstaller..." -ForegroundColor Cyan
pyinstaller --clean `
            --name "Affilabs-Core" `
            --onefile `
            --windowed `
            --add-data "ui;ui" `
            --add-data "config;config" `
            --add-data "detector_profiles;detector_profiles" `
            --add-data "led_calibration_official;led_calibration_official" `
            --add-data "servo_polarizer_calibration;servo_polarizer_calibration" `
            --add-data "settings;settings" `
            --hidden-import "PySide6" `
            --hidden-import "pyqtgraph" `
            --hidden-import "oceandirect" `
            --hidden-import "scipy" `
            --hidden-import "numpy" `
            --icon "ui/img/affinite2.ico" `
            --distpath "$DistDir" `
            main-simplified.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Executable built: dist/Affilabs-Core.exe" -ForegroundColor Green

    # Copy required data directories
    Write-Host "  [INFO] Copying data directories..." -ForegroundColor Cyan
    $RequiredDirs = @("config", "detector_profiles", "led_calibration_official", "servo_polarizer_calibration", "settings")
    foreach ($Dir in $RequiredDirs) {
        $SrcDir = Join-Path $WorkspaceRoot $Dir
        $DstDir = Join-Path $DistDir $Dir
        if (Test-Path $SrcDir) {
            Copy-Item -Recurse -Force $SrcDir $DstDir
            Write-Host "    [OK] Copied: $Dir/" -ForegroundColor Green
        }
    }

    # Copy documentation
    Copy-Item "README.md" -Destination (Join-Path $DistDir "README.md") -ErrorAction SilentlyContinue
    Write-Host "    [OK] Copied documentation" -ForegroundColor Green

    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "BUILD COMPLETE!" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable: dist/Affilabs-Core.exe" -ForegroundColor White
    Write-Host ""

    # Show file size
    $ExePath = Join-Path $DistDir "Affilabs-Core.exe"
    if (Test-Path $ExePath) {
        $ExeSize = (Get-Item $ExePath).Length / 1MB
        Write-Host "Size: $([math]::Round($ExeSize, 2)) MB" -ForegroundColor White
    }

    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  1. Test the executable" -ForegroundColor Gray
    Write-Host "  2. Verify hardware detection" -ForegroundColor Gray
    Write-Host "  3. Test calibration workflow" -ForegroundColor Gray
    Write-Host "  4. Ship to customers!" -ForegroundColor Gray

} else {
    Write-Host "  [ERROR] Executable build failed" -ForegroundColor Red
    Write-Host "Check the build log above for details" -ForegroundColor Yellow
    exit 1
}
