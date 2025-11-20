# PowerShell script to build the ezControl installer
# Prerequisites: Inno Setup 6 must be installed

param(
    [switch]$SkipDriverCheck = $false
)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  ezControl Installer Build Script" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Inno Setup is installed
$InnoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $InnoSetupPath)) {
    Write-Host "ERROR: Inno Setup 6 not found!" -ForegroundColor Red
    Write-Host "Please download and install from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host "Expected location: $InnoSetupPath" -ForegroundColor Yellow
    exit 1
}

Write-Host "[✓] Inno Setup 6 found" -ForegroundColor Green

# Check if ezControl.exe exists
$ExePath = "..\dist\ezControl.exe"
if (-not (Test-Path $ExePath)) {
    Write-Host "ERROR: ezControl.exe not found!" -ForegroundColor Red
    Write-Host "Expected location: $ExePath" -ForegroundColor Yellow
    Write-Host "Please build the executable first using PyInstaller" -ForegroundColor Yellow
    exit 1
}

Write-Host "[✓] ezControl.exe found" -ForegroundColor Green

# Check for required files
$warnings = @()

if (-not (Test-Path ".\drivers")) {
    $warnings += "Drivers folder not found - USB drivers won't be included"
    New-Item -ItemType Directory -Path ".\drivers" -Force | Out-Null
}

if (-not (Test-Path ".\redist")) {
    $warnings += "Redist folder not found - VC++ redistributable won't be included"
    New-Item -ItemType Directory -Path ".\redist" -Force | Out-Null
}

if (-not (Test-Path "..\LICENSE.txt")) {
    $warnings += "LICENSE.txt not found - creating placeholder"
    "MIT License`n`nCopyright (c) 2025`n`nPermission is hereby granted..." | Out-File "..\LICENSE.txt"
}

if (-not (Test-Path "..\icon.ico")) {
    $warnings += "icon.ico not found - installer will use default icon"
}

# Display warnings
if ($warnings.Count -gt 0 -and -not $SkipDriverCheck) {
    Write-Host ""
    Write-Host "WARNINGS:" -ForegroundColor Yellow
    foreach ($warning in $warnings) {
        Write-Host "  ⚠ $warning" -ForegroundColor Yellow
    }
    Write-Host ""
    $response = Read-Host "Continue anyway? (Y/N)"
    if ($response -ne "Y" -and $response -ne "y") {
        Write-Host "Build cancelled." -ForegroundColor Red
        exit 0
    }
}

# Build the installer
Write-Host ""
Write-Host "Building installer..." -ForegroundColor Cyan
Write-Host ""

try {
    $process = Start-Process -FilePath $InnoSetupPath `
                              -ArgumentList "ezControl_Setup.iss" `
                              -Wait `
                              -PassThru `
                              -NoNewWindow

    if ($process.ExitCode -eq 0) {
        Write-Host ""
        Write-Host "================================================" -ForegroundColor Green
        Write-Host "  BUILD SUCCESSFUL!" -ForegroundColor Green
        Write-Host "================================================" -ForegroundColor Green
        Write-Host ""

        # Find the output file
        $outputFile = Get-ChildItem -Path ".\output" -Filter "ezControl_Setup_*.exe" | Select-Object -First 1
        if ($outputFile) {
            $fileSize = [math]::Round($outputFile.Length / 1MB, 2)
            Write-Host "Installer created:" -ForegroundColor Green
            Write-Host "  Location: $($outputFile.FullName)" -ForegroundColor White
            Write-Host "  Size: $fileSize MB" -ForegroundColor White
            Write-Host ""
            Write-Host "The installer is ready for distribution!" -ForegroundColor Green

            # Ask if user wants to open the output folder
            $response = Read-Host "Open output folder? (Y/N)"
            if ($response -eq "Y" -or $response -eq "y") {
                Invoke-Item ".\output"
            }
        }
    } else {
        Write-Host ""
        Write-Host "BUILD FAILED!" -ForegroundColor Red
        Write-Host "Exit code: $($process.ExitCode)" -ForegroundColor Red
        Write-Host "Check the errors above for details." -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "ERROR: Build process failed!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
