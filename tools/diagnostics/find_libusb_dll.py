#!/usr/bin/env python
"""Find and verify libusbK DLL installation."""

import os
import sys
from pathlib import Path

print("=" * 80)
print("SEARCHING FOR LIBUSBK DLL")
print("=" * 80)

# Common locations to check
locations_to_check = [
    "C:\\Windows\\System32\\libusbK.dll",
    "C:\\Windows\\SysWOW64\\libusbK.dll",
    "C:\\Windows\\libusbK.dll",
    os.path.join(os.path.expandvars("%WINDIR%"), "System32", "libusbK.dll"),
    os.path.join(os.path.expandvars("%WINDIR%"), "SysWOW64", "libusbK.dll"),
]

# Also check in Python venv
venv_path = Path(__file__).parent / ".venv"
if venv_path.exists():
    locations_to_check.extend([
        str(venv_path / "Library" / "bin" / "libusbK.dll"),
        str(venv_path / "Lib" / "site-packages" / "libusbK.dll"),
    ])

# Also check in PATH
path_dirs = os.environ.get("PATH", "").split(os.pathsep)
for path_dir in path_dirs:
    locations_to_check.append(os.path.join(path_dir, "libusbK.dll"))

print("\nSearching for libusbK.dll...\n")

found_dlls = []
for location in locations_to_check:
    if os.path.exists(location):
        try:
            size = os.path.getsize(location)
            found_dlls.append((location, size))
            print(f"[FOUND] {location}")
            print(f"        Size: {size:,} bytes")
        except Exception as e:
            print(f"[ERROR] {location} - {e}")
    else:
        print(f"[NOT FOUND] {location}")

print("\n" + "=" * 80)

if found_dlls:
    print(f"\n[SUCCESS] Found {len(found_dlls)} libusbK.dll file(s):\n")
    for location, size in found_dlls:
        print(f"  {location} ({size:,} bytes)")

    # Try to test loading the first one
    print("\n" + "=" * 80)
    print("TESTING DLL LOADING")
    print("=" * 80)

    dll_path = found_dlls[0][0]
    print(f"\nAttempting to load: {dll_path}\n")

    try:
        import ctypes
        dll = ctypes.CDLL(dll_path)
        print("[OK] DLL loaded successfully!")
        print(f"Module: {dll}")
    except Exception as e:
        print(f"[ERROR] Failed to load DLL: {e}")

    # Now test if libusb can find it
    print("\n" + "=" * 80)
    print("TESTING LIBUSB INTEGRATION")
    print("=" * 80 + "\n")

    try:
        import usb.backend.libusb1
        backend = usb.backend.libusb1.get_backend()

        if backend:
            print("[OK] libusb1 backend initialized successfully!")
            print(f"Backend: {backend}")
            print(f"libusb library: {backend.lib}")
        else:
            print("[ERROR] libusb1 backend is None")
    except Exception as e:
        print(f"[ERROR] Failed to initialize libusb backend: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n[FAILED] libusbK.dll not found in any standard location!")
    print("\nTroubleshooting steps:")
    print("1. Verify Zadig installation:")
    print("   - Download from: https://zadig.akeo.ie/")
    print("   - Run Zadig.exe")
    print("   - Options > List All Devices")
    print("   - Select Ocean Optics device")
    print("   - Select driver: libusbK or libusb-win32")
    print("   - Click 'Replace Driver'")
    print("\n2. After installation, DLL should be at:")
    print("   C:\\Windows\\System32\\libusbK.dll")
    print("\n3. If still missing, manually download:")
    print("   https://github.com/libusb/libusb/releases/")
    print("   Extract and copy libusbK.dll to C:\\Windows\\System32\\")
