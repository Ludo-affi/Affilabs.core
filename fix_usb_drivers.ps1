# USB Driver Cleanup and Reset Script
# Run this as Administrator in PowerShell

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("="*69) -ForegroundColor Cyan
Write-Host "  USB DRIVER CLEANUP - Fix Corrupted Drivers from Failed Flash" -ForegroundColor Yellow
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("="*69) -ForegroundColor Cyan
Write-Host ""

Write-Host "This will:" -ForegroundColor White
Write-Host "  1. Remove all Raspberry Pi Pico USB drivers" -ForegroundColor Gray
Write-Host "  2. Clear USB device cache" -ForegroundColor Gray
Write-Host "  3. Force Windows to reinstall fresh drivers" -ForegroundColor Gray
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit
}

Write-Host "Step 1: Finding problem USB devices..." -ForegroundColor Cyan
Write-Host ""

# Find all Pico/RP2 devices
$picoDevices = Get-PnpDevice | Where-Object {
    $_.FriendlyName -like '*Pico*' -or 
    $_.FriendlyName -like '*RP2*' -or 
    $_.FriendlyName -like '*2E8A*' -or
    $_.HardwareID -like '*VID_2E8A*'
}

if ($picoDevices) {
    Write-Host "Found Pico-related devices:" -ForegroundColor Yellow
    $picoDevices | ForEach-Object {
        Write-Host "  - $($_.FriendlyName) [$($_.Status)]" -ForegroundColor White
    }
    Write-Host ""
} else {
    Write-Host "No Pico devices found in Device Manager" -ForegroundColor Gray
}

# Find all problem devices
$problemDevices = Get-PnpDevice | Where-Object {$_.Status -ne 'OK'}

if ($problemDevices) {
    Write-Host "Found devices with problems:" -ForegroundColor Red
    $problemDevices | ForEach-Object {
        Write-Host "  ! $($_.FriendlyName) [Problem: $($_.Problem)]" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "Step 2: Removing USB drivers..." -ForegroundColor Cyan
Write-Host ""

# Remove Pico devices
if ($picoDevices) {
    foreach ($device in $picoDevices) {
        Write-Host "Removing: $($device.FriendlyName)..." -ForegroundColor Yellow
        try {
            pnputil /remove-device $device.InstanceId /force 2>&1 | Out-Null
            Write-Host "  ✓ Removed" -ForegroundColor Green
        } catch {
            Write-Host "  ! Could not remove: $_" -ForegroundColor Red
        }
    }
    Write-Host ""
}

Write-Host "Step 3: Clearing USB driver cache..." -ForegroundColor Cyan
Write-Host ""

# Enumerate all USB devices and find Pico drivers
$drivers = pnputil /enum-drivers

# Look for 2E8A (Raspberry Pi Vendor ID)
$picoDrivers = $drivers | Select-String "2E8A" -Context 2,0

if ($picoDrivers) {
    Write-Host "Found Pico drivers in driver store:" -ForegroundColor Yellow
    
    # Extract .inf names
    foreach ($match in $picoDrivers) {
        $infMatch = $match.Context.PreContext | Select-String "Published Name.*:(.*\.inf)"
        if ($infMatch) {
            $infName = $infMatch.Matches.Groups[1].Value.Trim()
            Write-Host "Deleting driver: $infName..." -ForegroundColor Yellow
            try {
                pnputil /delete-driver $infName /force 2>&1 | Out-Null
                Write-Host "  ✓ Deleted" -ForegroundColor Green
            } catch {
                Write-Host "  ! Could not delete: $_" -ForegroundColor Red
            }
        }
    }
    Write-Host ""
}

Write-Host "Step 4: Rescanning USB devices..." -ForegroundColor Cyan
Write-Host ""

# Rescan hardware
pnputil /scan-devices 2>&1 | Out-Null
Write-Host "✓ Hardware rescan complete" -ForegroundColor Green
Write-Host ""

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("="*69) -ForegroundColor Cyan
Write-Host "  DRIVER CLEANUP COMPLETE" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("="*69) -ForegroundColor Cyan
Write-Host ""

Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. UNPLUG all USB devices from the panel mount" -ForegroundColor White
Write-Host "2. RESTART Windows (important!)" -ForegroundColor White
Write-Host "3. After restart, plug USB-C panel mount into computer" -ForegroundColor White
Write-Host "4. Plug USB-A hub into panel mount" -ForegroundColor White
Write-Host "5. Plug detector and controller into hub" -ForegroundColor White
Write-Host "6. Wait 30 seconds for Windows to install fresh drivers" -ForegroundColor White
Write-Host "7. Run: python test_usb_data.py" -ForegroundColor White
Write-Host ""

pause
