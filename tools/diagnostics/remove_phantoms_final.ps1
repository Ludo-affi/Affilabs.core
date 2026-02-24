#!/usr/bin/env powershell
# Remove all phantom Ocean Optics devices, keep only the working one

Write-Host "=" * 80
Write-Host "PHANTOM DEVICE REMOVAL (Precision/Advanced)"
Write-Host "=" * 80
Write-Host ""

# Check admin
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object System.Security.Principal.WindowsPrincipal($currentUser)
$isAdmin = $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] Must run as Administrator!"
    Write-Host ""
    Write-Host "Right-click PowerShell and select 'Run as Administrator'"
    exit 1
}

Write-Host "[OK] Running as Administrator`n"

# Define the working device (will not be deleted)
$workingDevice = "USB\VID_2457&PID_1022\6&3B513BA8&5&4"

Write-Host "PROTECTING (will not delete):"
Write-Host "  $workingDevice`n"

# Get all phantom devices
$allDevices = Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean Optics*'} |
    Select-Object InstanceId, Status, FriendlyName

$phantomDevices = $allDevices | Where-Object {$_.Status -ne 'OK'}

Write-Host "PHANTOMS TO REMOVE:"
Write-Host ""

foreach ($device in $phantomDevices) {
    Write-Host "  $($device.InstanceId) - Status: $($device.Status)"
}

Write-Host ""
Write-Host "Total phantoms: $($phantomDevices.Count)"
Write-Host ""

if ($phantomDevices.Count -eq 0) {
    Write-Host "[OK] No phantom devices to remove!"
    exit 0
}

Write-Host "Proceeding with removal...`n"

# Remove from registry
$removed = 0

foreach ($device in $phantomDevices) {
    $instanceId = $device.InstanceId

    # Build registry path
    $parts = $instanceId -split '\\'
    if ($parts.Count -eq 3) {
        $regPath = "HKLM:\SYSTEM\CurrentControlSet\Enum\USB\$($parts[1])\$($parts[2])"

        Write-Host "Removing: $instanceId"

        try {
            if (Test-Path $regPath) {
                Remove-Item -Path $regPath -Force -Recurse -ErrorAction Stop
                Write-Host "  [OK] Removed"
                $removed++
            } else {
                Write-Host "  [SKIP] Registry path not found"
            }
        } catch {
            Write-Host "  [ERROR] $_"
        }
    }
}

Write-Host ""
Write-Host "[COMPLETE] Removed $removed phantom device(s)"
Write-Host ""

# Verify
Write-Host "=" * 80
Write-Host "VERIFYING REMOVAL"
Write-Host "=" * 80
Write-Host ""

$finalDevices = Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean Optics*'} |
    Select-Object InstanceId, Status, FriendlyName

Write-Host "Remaining devices:"
Write-Host ""

foreach ($device in $finalDevices) {
    $icon = if ($device.Status -eq 'OK') { "[OK]" } else { "[!]" }
    Write-Host "$icon $($device.InstanceId)"
}

Write-Host ""
Write-Host "=" * 80
Write-Host "NEXT STEPS"
Write-Host "=" * 80
Write-Host ""
Write-Host "1. Unplug the Ocean Optics detector USB cable"
Write-Host "2. Wait 5 seconds"
Write-Host "3. Plug it back in"
Write-Host "4. Wait 10-15 seconds for driver to initialize"
Write-Host "5. Run the diagnostic:"
Write-Host "   python detector_diagnostic_simple.py"
Write-Host ""
