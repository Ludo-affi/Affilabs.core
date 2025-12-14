# Pico P4SPR Firmware Patch: Reboot to BOOTSEL (RPI-RP2)

Goal: Add a command (e.g., `ub`) that reboots the RP2040 into the USB bootloader without pressing BOOTSEL, enabling hands-free firmware updates via picotool or UF2 copy.

## One-file minimal diff

In your command parser source (where serial/USB commands are handled), apply this change.

```c
// Add at top of file (near other includes)
#include "pico/bootrom.h"

// ... inside your command processing function, add a case:
if (strcmp(cmd, "ub") == 0) {
    // Optional: send an ACK before rebooting so host sees the response
    // send_reply("OK: rebooting to bootloader\n");

    // Reboot into BOOTSEL (USB mass storage) mode
    reset_usb_boot(0, 0);
    // No return: device will re-enumerate as RPI-RP2
}
```

Notes:
- `reset_usb_boot()` is provided by the Pico SDK (`pico/bootrom.h`).
- Parameters `(0, 0)` are standard for rebooting into BOOTSEL.
- Make sure any ongoing PWM/IO is left as-is; the reboot will reset hardware.

## Typical integration locations
- File names often used: `affinite_p4spr.c`, `main.c`, or a `command_parser.c`.
- Place the `#include` at file scope and the `if (strcmp(cmd, "ub") == 0)` inside your main command dispatch.

## Build and flash (first time)
- Build your V1.1 firmware with this patch.
- Flash once via SWD or any available method.
- After this, future updates are BOOTSEL-free:
  1. Device connected in normal mode.
  2. Host sends `ub` (or use `picotool reboot --bootloader` if supported).
  3. Device appears as RPI-RP2; copy new UF2.

## Optional: Picotool route
If you prefer picotool to initiate the reboot:
- Ensure USB descriptor/device supports picotool `reboot --bootloader` (usually works with standard Pico SDK builds).
- Picotool command:
```
picotool reboot --bootloader
```
Then copy UF2 to the new drive letter.

## Safety recommendations
- Only allow `ub` in idle/safe states (no critical motion active).
- Reply to the host before rebooting to avoid host-side timeouts.
- Document the command in your protocol README.

## Quick test sequence
1. Flash patched V1.1.
2. Open your serial console and send `ub`.
3. Confirm device re-enumerates as `RPI-RP2` mass storage.
4. Copy `affinite_p4spr_v1.2.uf2` to the drive.
5. Device reboots into new firmware.

---
This patch is portable and minimal; your picoezspr flow likely already uses the same `reset_usb_boot()` mechanism.
