# Automatic driver fix for Unknown status COM ports
# Run as Administrator

Write-Host "=" -NoNewline
Write-Host ("=" * 69)
Write-Host "AUTOMATIC DRIVER FIX FOR COM PORTS"
Write-Host ("=" * 70)

# Get all USB Serial Devices with Unknown status
$devices = Get-PnpDevice | Where-Object {
    $_.FriendlyName -like '*USB Serial*' -and
    $_.Status -eq 'Unknown'
}

if ($devices.Count -eq 0) {
    Write-Host "`nNo devices with 'Unknown' status found."
    Write-Host "Your devices might already be working!"
    exit
}

Write-Host "`nFound $($devices.Count) device(s) with Unknown status:"
foreach ($dev in $devices) {
    Write-Host "  - $($dev.FriendlyName) [$($dev.InstanceId.Substring(0, 40))...]"
}

Write-Host "`n" -NoNewline
Write-Host ("=" * 70)
Write-Host "ATTEMPTING TO FIX DRIVERS..."
Write-Host ("=" * 70)

$fixed = 0
$failed = 0

foreach ($dev in $devices) {
    Write-Host "`nProcessing: $($dev.FriendlyName)"

    try {
        # Disable device
        Write-Host "  Disabling..."
        Disable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false -ErrorAction Stop
        Start-Sleep -Milliseconds 500

        # Re-enable device
        Write-Host "  Re-enabling..."
        Enable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false -ErrorAction Stop
        Start-Sleep -Milliseconds 500

        # Check if it worked
        $updated = Get-PnpDevice -InstanceId $dev.InstanceId
        if ($updated.Status -eq 'OK') {
            Write-Host "  ✓ SUCCESS! Device now has OK status" -ForegroundColor Green
            $fixed++
        } else {
            Write-Host "  ✗ Still has Unknown status" -ForegroundColor Yellow
            $failed++
        }
    }
    catch {
        Write-Host "  ✗ ERROR: $_" -ForegroundColor Red
        $failed++
    }
}

Write-Host "`n" -NoNewline
Write-Host ("=" * 70)
Write-Host "RESULTS"
Write-Host ("=" * 70)
Write-Host "Fixed: $fixed"
Write-Host "Failed: $failed"

if ($fixed -gt 0) {
    Write-Host "`n✓ Run 'python test_direct_controller.py' to test connection!" -ForegroundColor Green
} else {
    Write-Host "`n✗ No devices were fixed. Try unplugging and replugging devices." -ForegroundColor Yellow
}

Write-Host ("=" * 70)
