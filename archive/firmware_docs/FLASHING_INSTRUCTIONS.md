# Firmware Flashing Instructions for PicoP4SPR

## Software Method (Preferred - No Manual Button Press Required)

### Quick Method
Run the automated flash script:
```powershell
.\.venv312\Scripts\python.exe flash_v19_firmware.py
```

### Manual Software Method (If Script Fails)

**Step 1: Trigger Bootloader Mode**

The RP2040 chip enters bootloader mode when you connect at 1200 baud. This can be done entirely via software:

```python
import serial
import time

# Open COM4 at 1200 baud - this triggers bootloader mode
ser = serial.Serial("COM4", 1200, timeout=1)
time.sleep(0.3)
ser.close()
# Device will disconnect from COM4 and reappear as a USB drive
```

Or via PowerShell one-liner:
```powershell
.\.venv312\Scripts\python.exe -c "import serial,time; s=serial.Serial('COM4',1200); time.sleep(0.3); s.close()"
```

**Step 2: Verify RPI-RP2 Drive Appeared**

After 2-3 seconds, check for the drive:
```powershell
Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Description -like "*RP2*"}
```

The device will appear as a removable drive with the label "RPI-RP2" (typically D:, E:, or F:)

**Step 3: Copy Firmware**

```powershell
Copy-Item "firmware\affinite_p4spr_v1.9.uf2" "D:\affinite_p4spr_v1.9.uf2"
```
(Replace D: with whatever drive letter appeared)

**Step 4: Automatic Reboot**

The Pico automatically reboots after the .uf2 file is copied. Within 2-3 seconds:
- The RPI-RP2 drive disappears
- The device returns as COM4
- New firmware is running

**Step 5: Verify Success**

```powershell
Get-CimInstance -ClassName Win32_PnPEntity | Where-Object {$_.Name -like "*COM4*"}
```

Should show "USB Serial Device (COM4)" with Status: OK

---

## Manual Hardware Method (Fallback)

Only use if software method fails due to COM port access issues.

1. **Unplug USB cable** from the Pico
2. **Hold down BOOTSEL button** (small white button on Pico board)
3. **Plug USB cable back in** while holding BOOTSEL
4. **Release BOOTSEL button**
5. RPI-RP2 drive should appear in File Explorer
6. **Copy firmware file** to the drive
7. Device automatically reboots

---

## Troubleshooting

### "Cannot configure port" or "PermissionError"
- Another program is using COM4
- Close any terminal programs, Python scripts, or other apps connected to COM4
- Try the software method again

### COM4 disappears but no RPI-RP2 drive appears
- Wait 5-10 seconds (some systems are slow)
- Check Device Manager for "RPI-RP2" under "Universal Serial Bus devices"
- Try unplugging and plugging USB cable back in
- Fall back to manual hardware method

### Drive appears but firmware copy fails
- Check that you have write permissions
- Verify the .uf2 file exists at: `firmware\affinite_p4spr_v1.9.uf2`
- Try copying manually through File Explorer

---

## Firmware Versions

| Version | File | Notes |
|---------|------|-------|
| v1.9 | `affinite_p4spr_v1.9.uf2` | Current stable version |

---

## Technical Details

**Why 1200 baud triggers bootloader:**
The RP2040 chip has a special feature where connecting at 1200 baud and immediately disconnecting signals it to reset into USB bootloader mode (BOOTSEL mode). This is a standard Arduino-style bootloader trigger method.

**What happens during flash:**
1. RP2040 reboots into ROM bootloader
2. Presents itself as USB Mass Storage device
3. Monitors for .uf2 file writes
4. When .uf2 detected, flashes it to internal flash memory
5. Automatically reboots into new firmware
6. Returns to normal operation on COM4

**Why .uf2 format:**
UF2 (USB Flashing Format) is designed for drag-and-drop flashing. It contains:
- Binary firmware data
- Flash address information
- Checksums for verification
- All in a format that looks like a normal file to the OS
