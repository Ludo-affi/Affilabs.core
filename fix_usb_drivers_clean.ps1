# USB Driver Cleanup Script
# Run as Administrator

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  USB DRIVER CLEANUP - Fix Corrupted Drivers" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: Must run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit
}

Write-Host "Step 1: Finding Pico devices..." -ForegroundColor Cyan
Write-Host ""

# Find all Pico/RP2 devices
$picoDevices = Get-PnpDevice | Where-Object {
    $_.FriendlyName -like '*Pico*' -or 
    $_.FriendlyName -like '*RP2*' -or 
    $_.FriendlyName -like '*2E8A*' -or
    $_.HardwareID -like '*VID_2E8A*'
}

if ($picoDevices) {
    Write-Host "Found Pico devices:" -ForegroundColor Yellow
    foreach ($dev in $picoDevices) {
        Write-Host "  - $($dev.FriendlyName) [$($dev.Status)]" -ForegroundColor White
    }
} else {
    Write-Host "No Pico devices found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Step 2: Removing devices..." -ForegroundColor Cyan
Write-Host ""

if ($picoDevices) {
    foreach ($device in $picoDevices) {
        Write-Host "Removing: $($device.FriendlyName)..." -ForegroundColor Yellow
        try {
            pnputil /remove-device $device.InstanceId /force 2>&1 | Out-Null
            Write-Host "  Done" -ForegroundColor Green
        } catch {
            Write-Host "  Could not remove" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "Step 3: Clearing driver cache..." -ForegroundColor Cyan
Write-Host ""

# Get all drivers
$allDrivers = pnputil /enum-drivers

# Find Pico drivers (Vendor ID 2E8A)
$foundPicoDrivers = $false
$driverLines = $allDrivers -split "`n"

for ($i = 0; $i -lt $driverLines.Length; $i++) {
    if ($driverLines[$i] -match "2E8A") {
        # Look backwards for the Published Name
        for ($j = $i; $j -ge ($i - 10) -and $j -ge 0; $j--) {
            if ($driverLines[$j] -match "Published Name\s*:\s*(oem\d+\.inf)") {
                $infName = $matches[1]
                Write-Host "Deleting driver: $infName" -ForegroundColor Yellow
                pnputil /delete-driver $infName /force 2>&1 | Out-Null
                $foundPicoDrivers = $true
                break
            }
        }
    }
}

if (-not $foundPicoDrivers) {
    Write-Host "No Pico drivers found in driver store" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Step 4: Rescanning..." -ForegroundColor Cyan
pnputil /scan-devices 2>&1 | Out-Null
Write-Host "Done" -ForegroundColor Green
Write-Host ""

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  CLEANUP COMPLETE" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. UNPLUG all devices" -ForegroundColor White
Write-Host "2. RESTART Windows" -ForegroundColor White
Write-Host "3. After restart, plug devices back in through panel mount" -ForegroundColor White
Write-Host "4. Wait 30 seconds" -ForegroundColor White
Write-Host "5. Run: python test_usb_data.py" -ForegroundColor White
Write-Host ""

pause
