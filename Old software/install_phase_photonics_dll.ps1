# Copy PhasePhotonics DLL to main utils folder
# Run this when ready to implement PhasePhotonics detector

Write-Host "PhasePhotonics DLL Installation Script" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

$sourceDLL = "Phase Photonics Modifications\utils\SensorT_x64.dll"
$destDLL = "utils\SensorT_x64.dll"

# Check if source exists
if (-not (Test-Path $sourceDLL)) {
    Write-Host "ERROR: Source DLL not found: $sourceDLL" -ForegroundColor Red
    Write-Host "Expected location: Old software\$sourceDLL" -ForegroundColor Yellow
    exit 1
}

# Check if destination already exists
if (Test-Path $destDLL) {
    Write-Host "WARNING: Destination DLL already exists: $destDLL" -ForegroundColor Yellow
    $response = Read-Host "Overwrite? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Host "Installation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# Copy DLL
try {
    Copy-Item $sourceDLL -Destination $destDLL -Force
    Write-Host "✓ Successfully copied DLL" -ForegroundColor Green
    Write-Host "  From: $sourceDLL" -ForegroundColor Gray
    Write-Host "  To:   $destDLL" -ForegroundColor Gray
    Write-Host ""

    # Verify
    if (Test-Path $destDLL) {
        $fileInfo = Get-Item $destDLL
        Write-Host "✓ Verified: DLL installed successfully" -ForegroundColor Green
        Write-Host "  Size: $($fileInfo.Length) bytes" -ForegroundColor Gray
        Write-Host "  Modified: $($fileInfo.LastWriteTime)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Next Steps:" -ForegroundColor Cyan
        Write-Host "1. Implement methods in utils\phase_photonics_wrapper.py" -ForegroundColor White
        Write-Host "2. Update utils\SpectrometerAPI.py (SENSOR_DATA_LEN = 1848)" -ForegroundColor White
        Write-Host "3. Install dependencies: pip install ftd2xx" -ForegroundColor White
        Write-Host "4. Test thoroughly before setting IS_PLACEHOLDER = False" -ForegroundColor White
        Write-Host "5. Update config.json: detector_type = 'PhasePhotonics'" -ForegroundColor White
    } else {
        Write-Host "ERROR: Copy succeeded but verification failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "ERROR: Failed to copy DLL: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Installation complete! ✓" -ForegroundColor Green
