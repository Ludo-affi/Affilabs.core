# Automated Pico SDK Installation and Firmware Build Script
# Run from firmware/pico_p4spr directory

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PicoP4SPR Firmware Build Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check prerequisites
Write-Host "Step 1: Checking prerequisites..." -ForegroundColor Yellow

# Check Git
try {
    $gitVersion = git --version
    Write-Host "✅ Git found: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Git not found" -ForegroundColor Red
    Write-Host "Please install Git for Windows: https://gitforwindows.org/" -ForegroundColor Yellow
    Write-Host "Then restart PowerShell and run this script again." -ForegroundColor Yellow
    exit 1
}

# Check CMake
try {
    $cmakeVersion = cmake --version | Select-Object -First 1
    Write-Host "✅ CMake found: $cmakeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ CMake not found" -ForegroundColor Red
    Write-Host "Install options:" -ForegroundColor Yellow
    Write-Host "  1. Chocolatey: choco install cmake -y" -ForegroundColor Yellow
    Write-Host "  2. Download: https://cmake.org/download/" -ForegroundColor Yellow
    Write-Host "Then restart PowerShell and run this script again." -ForegroundColor Yellow
    exit 1
}

# Check ARM GCC
try {
    $gccVersion = arm-none-eabi-gcc --version | Select-Object -First 1
    Write-Host "✅ ARM GCC found: $gccVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ ARM GCC not found" -ForegroundColor Red
    Write-Host "Install options:" -ForegroundColor Yellow
    Write-Host "  1. Chocolatey: choco install gcc-arm-embedded -y" -ForegroundColor Yellow
    Write-Host "  2. Download: https://developer.arm.com/downloads/-/gnu-rm" -ForegroundColor Yellow
    Write-Host "Then restart PowerShell and run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Step 2: Install Pico SDK
Write-Host "Step 2: Installing Pico SDK..." -ForegroundColor Yellow

$sdkPath = "C:\pico-sdk"

if (Test-Path $sdkPath) {
    Write-Host "✅ Pico SDK already exists at $sdkPath" -ForegroundColor Green

    # Update to latest
    Write-Host "   Updating to latest version..." -ForegroundColor Cyan
    Push-Location $sdkPath
    git pull
    git submodule update --init --recursive
    Pop-Location
} else {
    Write-Host "   Cloning Pico SDK from GitHub..." -ForegroundColor Cyan
    Push-Location C:\

    try {
        git clone https://github.com/raspberrypi/pico-sdk.git
        Set-Location pico-sdk

        Write-Host "   Initializing submodules (this may take a few minutes)..." -ForegroundColor Cyan
        git submodule update --init --recursive

        Pop-Location
        Write-Host "✅ Pico SDK installed successfully" -ForegroundColor Green
    } catch {
        Pop-Location
        Write-Host "❌ Failed to clone Pico SDK" -ForegroundColor Red
        Write-Host "Error: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# Step 3: Set environment variable
Write-Host "Step 3: Setting PICO_SDK_PATH environment variable..." -ForegroundColor Yellow

# Set for current session
$env:PICO_SDK_PATH = $sdkPath

# Set permanently for user
[System.Environment]::SetEnvironmentVariable("PICO_SDK_PATH", $sdkPath, "User")

Write-Host "✅ PICO_SDK_PATH = $sdkPath" -ForegroundColor Green
Write-Host ""

# Step 4: Build firmware
Write-Host "Step 4: Building firmware..." -ForegroundColor Yellow

# Create build directory
if (-not (Test-Path "build")) {
    New-Item -ItemType Directory -Path "build" | Out-Null
}

Push-Location build

try {
    # Configure with CMake
    Write-Host "   Running CMake configuration..." -ForegroundColor Cyan
    cmake .. -G "Ninja" -DPICOTOOL_FETCH_FROM_GIT=OFF

    if ($LASTEXITCODE -ne 0) {
        throw "CMake configuration failed"
    }

    # Build
    Write-Host "   Compiling firmware..." -ForegroundColor Cyan
    cmake --build . --config Release

    if ($LASTEXITCODE -ne 0) {
        throw "Build failed"
    }

    # Check output
    if (Test-Path "affinite_p4spr.uf2") {
        $fileSize = (Get-Item "affinite_p4spr.uf2").Length
        Write-Host ""
        Write-Host "✅ Build successful!" -ForegroundColor Green
        Write-Host "   Output: $(Get-Location)\affinite_p4spr.uf2 ($fileSize bytes)" -ForegroundColor Green

        # Copy to firmware directory
        Copy-Item "affinite_p4spr.uf2" "..\affinite_p4spr.uf2" -Force
        Write-Host "✅ Copied to firmware\pico_p4spr\affinite_p4spr.uf2" -ForegroundColor Green
    } else {
        throw "Build output file not found"
    }

} catch {
    Pop-Location
    Write-Host ""
    Write-Host "❌ Build failed: $_" -ForegroundColor Red
    exit 1
}

Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ FIRMWARE BUILD COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next step: Flash the firmware to your Pico (FIRST TIME ONLY)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Manual flash process:" -ForegroundColor Cyan
Write-Host "  1. Disconnect PicoP4SPR from USB"
Write-Host "  2. Hold BOOTSEL button on the Pico"
Write-Host "  3. Connect USB while holding BOOTSEL"
Write-Host "  4. Release BOOTSEL - Pico appears as RPI-RP2 drive"
Write-Host "  5. Copy firmware\pico_p4spr\affinite_p4spr.uf2 to RPI-RP2 drive"
Write-Host "  6. Pico reboots with V1.1"
Write-Host ""
Write-Host "After this first manual flash, all future updates are automatic!" -ForegroundColor Green
Write-Host ""
