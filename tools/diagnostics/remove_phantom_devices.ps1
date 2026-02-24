# Remove phantom Ocean Optics devices, keep only the real one (Status: OK)
# Run as Administrator

Write-Host "=========================================="
Write-Host "PHANTOM DEVICE REMOVAL SCRIPT"
Write-Host "=========================================="
Write-Host ""

$devices = @(Get-PnpDevice -FriendlyName '*FLAME-T*')
Write-Host "Found $($devices.Count) FLAME-T device entries`n"

$removed = 0
$kept = 0

foreach ($device in $devices) {
    $status = $device.Status
    $id = $device.InstanceId
    
    if ($status -eq "OK") {
        Write-Host "[KEEP] $id (Status: OK - REAL DEVICE)"
        $kept++
    } else {
        Write-Host "[REMOVE] $id (Status: $status - PHANTOM)"
        try {
            Remove-PnpDevice -InstanceId $id -Confirm:$false -Force -ErrorAction Stop
            Write-Host "  ✓ Removed"
            $removed++
        } catch {
            Write-Host "  ✗ Failed: $_"
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "RESULTS: Removed $removed phantom devices, kept $kept real device"
Write-Host "=========================================="
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Unplug detector from USB"
Write-Host "2. Wait 5 seconds"
Write-Host "3. Plug detector back in"
Write-Host "4. Run diagnostic: python detector_diagnostic_simple.py"
