# Automatic Firmware V1.2 Flash Script
# This script waits for the Pico in bootloader mode and automatically copies the firmware

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Firmware V1.2 Flash Tool" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Instructions:" -ForegroundColor Yellow
Write-Host "1. Disconnect Pico from USB"
Write-Host "2. Hold BOOTSEL button on the Pico"
Write-Host "3. Connect USB while holding BOOTSEL"
Write-Host "4. Release BOOTSEL button"
Write-Host "`nWaiting for RPI-RP2 drive...`n" -ForegroundColor Cyan

$timeout = 120  # 2 minutes
$start = Get-Date

while (((Get-Date) - $start).TotalSeconds -lt $timeout) {
    $drive = Get-Volume | Where-Object { $_.FileSystemLabel -eq "RPI-RP2" } | Select-Object -First 1

    if ($drive) {
        $driveLetter = $drive.DriveLetter + ":"
        Write-Host "✅ Found RPI-RP2 at $driveLetter" -ForegroundColor Green
        Write-Host "`nCopying firmware V1.2..." -ForegroundColor Yellow

        try {
            Copy-Item "firmware\pico_p4spr\affinite_p4spr_v1.2.uf2" "$driveLetter\" -Force

            Write-Host "`n========================================" -ForegroundColor Green
            Write-Host "  🎉 Firmware V1.2 Flashed!" -ForegroundColor Green
            Write-Host "========================================" -ForegroundColor Green
            Write-Host "`nPico will reboot automatically in a few seconds..." -ForegroundColor Cyan
            Write-Host "New features: rank command for fast LED calibration`n" -ForegroundColor Cyan

            exit 0
        }
        catch {
            Write-Host "`n❌ Failed to copy firmware: $_" -ForegroundColor Red
            exit 1
        }
    }

    Start-Sleep -Milliseconds 500
}

Write-Host "`n❌ RPI-RP2 drive not found after $timeout seconds" -ForegroundColor Red
Write-Host "`nPlease check:" -ForegroundColor Yellow
Write-Host "- Pico is connected in bootloader mode (hold BOOTSEL while plugging in)"
Write-Host "- USB cable is working"
Write-Host "`nOr manually copy: firmware\pico_p4spr\affinite_p4spr_v1.2.uf2"
Write-Host "To: RPI-RP2 drive`n"
