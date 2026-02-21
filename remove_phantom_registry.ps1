#!/usr/bin/env powershell
"""Remove phantom Ocean Optics devices via Registry (PowerShell)."""

Write-Host "=" * 80
Write-Host "REMOVING PHANTOM OCEAN OPTICS DEVICES"
Write-Host "=" * 80
Write-Host ""

# Check if running as admin
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object System.Security.Principal.WindowsPrincipal($currentUser)
$isAdmin = $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator!"
    Write-Host ""
    Write-Host "Please right-click on PowerShell and select 'Run as Administrator'"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Running as Administrator`n"

# List current devices
Write-Host "Current Ocean Optics devices:"
Write-Host ""
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean*FLAME*'} |
Select-Object @{n='Name';e={$_.FriendlyName}}, Status, InstanceId |
Format-Table -AutoSize

$devices = Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean*FLAME*'} |
Select-Object InstanceId, Status, ConfigManagerErrorCode

$phantomDevices = $devices | Where-Object {$_.Status -eq 'Unknown' -or $_.ConfigManagerErrorCode -ne 0}
$workingDevices = $devices | Where-Object {$_.Status -eq 'OK' -and $_.ConfigManagerErrorCode -eq 0}

Write-Host "Summary:"
Write-Host "  Working devices: $($workingDevices.Count)"
Write-Host "  Phantom devices: $($phantomDevices.Count)"
Write-Host ""

if ($phantomDevices.Count -eq 0) {
    Write-Host "[OK] No phantom devices found!"
    exit 0
}

# Remove via registry
Write-Host "Removing phantom devices via registry..."
Write-Host ""

$regPath = "HKLM:\SYSTEM\CurrentControlSet\Enum\USB"

if (-not (Test-Path $regPath)) {
    Write-Host "[ERROR] USB registry path not found"
    exit 1
}

$removed = 0

foreach ($phantomId in $phantomDevices.InstanceId) {
    # Convert InstanceId to registry path
    # InstanceId format: USB\VID_2457&PID_1022\7&2980B0FF&0&2
    # Registry path: HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_2457&PID_1022\7&2980B0FF&0&2

    $parts = $phantomId -split '\\'
    if ($parts.Count -eq 3) {
        $regSubPath = "$regPath\$($parts[1])\$($parts[2])"

        Write-Host "Removing: $phantomId"
        Write-Host "  Registry path: $regSubPath"

        try {
            if (Test-Path $regSubPath) {
                Remove-Item -Path $regSubPath -Force -ErrorAction Stop -Recurse
                Write-Host "  [OK] Removed from registry"
                $removed++
            } else {
                Write-Host "  [SKIPPED] Path not found"
            }
        } catch {
            Write-Host "  [ERROR] $_"
        }
    }
}

Write-Host ""
Write-Host "Removed $removed phantom device(s) from registry"

# Now rescan
Write-Host ""
Write-Host "Rescanning USB devices..."

$shell = New-Object -ComObject Shell.Application
$shell.Windows() | Where-Object {$_.Name -like '*explorer*'} | ForEach-Object {
    $_.refresh()
}

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "=" * 80
Write-Host "FINAL STATUS"
Write-Host "=" * 80
Write-Host ""

$finalDevices = Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean*FLAME*'} |
Select-Object @{n='Name';e={$_.FriendlyName}}, Status, InstanceId

Write-Host "Current Ocean Optics devices:"
Write-Host ""
$finalDevices | Format-Table -AutoSize

Write-Host ""
Write-Host "=" * 80
Write-Host "NEXT STEPS"
Write-Host "=" * 80
Write-Host ""
Write-Host "1. Close this window"
Write-Host "2. Unplug the Ocean Optics USB cable"
Write-Host "3. Wait 5 seconds"
Write-Host "4. Plug it back in"
Write-Host "5. Run the diagnostic:"
Write-Host "   python detector_diagnostic_simple.py"
Write-Host ""
