# Affilabs-Core Production Shipping Script
# Automated workspace preparation and packaging

param(
    [string]$Version = "1.0.0-beta",
    [string]$Target = "all",  # Options: exe, source, all
    [switch]$SkipTests = $false,
    [switch]$Clean = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "AFFILABS-CORE PRODUCTION SHIPPING" -ForegroundColor Cyan
Write-Host "Version: $Version" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Configuration
$WorkspaceRoot = $PSScriptRoot
$DistDir = Join-Path $WorkspaceRoot "dist"
$OutputDir = Join-Path $DistDir "Affilabs-Core-v$Version"

# Step 1: Clean previous builds
if ($Clean) {
    Write-Host "[1/7] Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path $DistDir) {
        Remove-Item -Recurse -Force $DistDir
        Write-Host "  ✅ Cleaned dist/" -ForegroundColor Green
    }
    if (Test-Path "build") {
        Remove-Item -Recurse -Force "build"
        Write-Host "  ✅ Cleaned build/" -ForegroundColor Green
    }
} else {
    Write-Host "[1/7] Skipping clean (use -Clean to clean)" -ForegroundColor Gray
}

# Step 2: Activate virtual environment
Write-Host "[2/7] Activating virtual environment..." -ForegroundColor Yellow
$VenvActivate = Join-Path $WorkspaceRoot ".venv312\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    & $VenvActivate
    Write-Host "  ✅ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "  ❌ Virtual environment not found: $VenvActivate" -ForegroundColor Red
    exit 1
}

# Step 3: Verify Python version
Write-Host "[3/7] Verifying Python version..." -ForegroundColor Yellow
$PythonVersion = python --version 2>&1
if ($PythonVersion -match "Python 3\.12") {
    Write-Host "  ✅ $PythonVersion" -ForegroundColor Green
} else {
    Write-Host "  ❌ Python 3.12+ required, found: $PythonVersion" -ForegroundColor Red
    exit 1
}

# Step 4: Run tests (optional)
if (-not $SkipTests) {
    Write-Host "[4/7] Running tests..." -ForegroundColor Yellow

    # Check if pytest is available
    $HasPytest = python -c "import pytest" 2>&1
    if ($LASTEXITCODE -eq 0) {
        pytest tests/ -v --tb=short
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ All tests passed" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  Some tests failed - continue anyway? (Y/N)" -ForegroundColor Yellow
            $Continue = Read-Host
            if ($Continue -ne "Y") {
                exit 1
            }
        }
    } else {
        Write-Host "  ⚠️  pytest not found, skipping tests" -ForegroundColor Yellow
    }
} else {
    Write-Host "[4/7] Skipping tests (-SkipTests enabled)" -ForegroundColor Gray
}

# Step 5: Organize workspace
Write-Host "[5/7] Organizing workspace..." -ForegroundColor Yellow
python prepare_for_shipping.py --execute
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Workspace organized" -ForegroundColor Green
} else {
    Write-Host "  ❌ Workspace organization failed" -ForegroundColor Red
    exit 1
}

# Step 6: Create output directory
Write-Host "[6/7] Creating output directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
Write-Host "  ✅ Created: $OutputDir" -ForegroundColor Green

# Step 7: Build targets
Write-Host "[7/7] Building targets..." -ForegroundColor Yellow

if ($Target -eq "exe" -or $Target -eq "all") {
    Write-Host "  📦 Building standalone executable..." -ForegroundColor Cyan

    # Check if PyInstaller is installed
    $HasPyInstaller = python -c "import PyInstaller" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  📥 Installing PyInstaller..." -ForegroundColor Yellow
        pip install pyinstaller
    }

    # Build executable
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
        Write-Host "  ✅ Executable built: dist/Affilabs-Core.exe" -ForegroundColor Green

        # Copy required data directories
        $RequiredDirs = @("config", "detector_profiles", "led_calibration_official", "servo_polarizer_calibration")
        foreach ($Dir in $RequiredDirs) {
            $SrcDir = Join-Path $WorkspaceRoot $Dir
            $DstDir = Join-Path $DistDir $Dir
            if (Test-Path $SrcDir) {
                Copy-Item -Recurse -Force $SrcDir $DstDir
                Write-Host "  ✅ Copied: $Dir/" -ForegroundColor Green
            }
        }

        # Copy documentation
        Copy-Item "README.md" -Destination (Join-Path $DistDir "README.md")
        Copy-Item "SHIPPING_GUIDE.md" -Destination (Join-Path $DistDir "SHIPPING_GUIDE.md")
        Write-Host "  ✅ Copied documentation" -ForegroundColor Green

    } else {
        Write-Host "  ❌ Executable build failed" -ForegroundColor Red
    }
}

if ($Target -eq "source" -or $Target -eq "all") {
    Write-Host "  📦 Creating source package..." -ForegroundColor Cyan

    python prepare_for_shipping.py --package --output $DistDir
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Source package created" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Source package creation failed" -ForegroundColor Red
    }
}

# Generate checksums
Write-Host ""
Write-Host "Generating checksums..." -ForegroundColor Yellow
Get-ChildItem $DistDir -Recurse -File | Where-Object { $_.Extension -in ".exe", ".zip" } | ForEach-Object {
    $Hash = Get-FileHash $_.FullName -Algorithm SHA256
    $HashFile = "$($_.FullName).sha256"
    "$($Hash.Hash)  $($_.Name)" | Out-File -FilePath $HashFile -Encoding UTF8
    Write-Host "  ✅ $($_.Name).sha256" -ForegroundColor Green
}

# Final summary
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "SHIPPING PACKAGE READY!" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "Location: $DistDir" -ForegroundColor White
Write-Host ""
Write-Host "Contents:" -ForegroundColor White
Get-ChildItem $DistDir -Recurse | Where-Object { -not $_.PSIsContainer } | ForEach-Object {
    $Size = "{0:N2} MB" -f ($_.Length / 1MB)
    Write-Host "  - $($_.Name) ($Size)" -ForegroundColor Gray
}
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Test the executable on a clean machine" -ForegroundColor Gray
Write-Host "  2. Verify hardware detection works" -ForegroundColor Gray
Write-Host "  3. Test calibration workflow" -ForegroundColor Gray
Write-Host "  4. Create GitHub release" -ForegroundColor Gray
Write-Host "  5. Ship to customers!" -ForegroundColor Gray
Write-Host ""
Write-Host "Done!" -ForegroundColor Green
