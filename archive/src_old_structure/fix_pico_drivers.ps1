# Fix Pico controller drivers by disabling and re-enabling the devices

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Pico Controller Driver Reset Tool" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Get all Pico USB Serial devices (VID_2E8A&PID_000A)
$picoDevices = Get-PnpDevice | Where-Object {
    $_.InstanceId -like "*VID_2E8A*PID_000A*" -and
    $_.FriendlyName -like "*USB Serial*"
}

if ($picoDevices.Count -eq 0) {
    Write-Host "No Pico controllers found" -ForegroundColor Yellow
    exit
}

Write-Host "Found $($picoDevices.Count) Pico controller(s):`n" -ForegroundColor Green

foreach ($device in $picoDevices) {
    Write-Host "  - $($device.FriendlyName) [Status: $($device.Status)]" -ForegroundColor White
    Write-Host "    Instance: $($device.InstanceId)" -ForegroundColor Gray
}

Write-Host "`nAttempting to reset devices..." -ForegroundColor Yellow
Write-Host "This will disable and re-enable each device to reload drivers.`n" -ForegroundColor Yellow

foreach ($device in $picoDevices) {
    Write-Host "Processing: $($device.FriendlyName)..." -ForegroundColor Cyan

    try {
        # Disable the device
        Write-Host "  Disabling..." -ForegroundColor Gray
        Disable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false -ErrorAction Stop
        Start-Sleep -Seconds 2

        # Re-enable the device
        Write-Host "  Re-enabling..." -ForegroundColor Gray
        Enable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false -ErrorAction Stop
        Start-Sleep -Seconds 2

        Write-Host "  ✓ Reset complete" -ForegroundColor Green
    }
    catch {
        Write-Host "  ✗ Failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Checking device status after reset..." -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

Start-Sleep -Seconds 2

$picoDevices = Get-PnpDevice | Where-Object {
    $_.InstanceId -like "*VID_2E8A*PID_000A*" -and
    $_.FriendlyName -like "*USB Serial*"
}

foreach ($device in $picoDevices) {
    $status = $device.Status
    $color = if ($status -eq "OK") { "Green" } else { "Yellow" }
    Write-Host "  $($device.FriendlyName): $status" -ForegroundColor $color
}

Write-Host "`nDone! Try connecting again in the application." -ForegroundColor Cyan
