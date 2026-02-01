"""Check pyusb backend status and attempt to fix."""
import sys

print("=" * 70)
print("PYUSB BACKEND DIAGNOSTIC")
print("=" * 70)

print("\n1. Checking for pyusb...")
try:
    import usb.core
    print("   ✅ pyusb is installed")
except ImportError:
    print("   ❌ pyusb is NOT installed")
    print("   Run: pip install pyusb")
    sys.exit(1)

print("\n2. Checking for libusb backend...")
try:
    # Try to find a device (any device)
    device = usb.core.find()
    if device is None:
        print("   ⚠️  Backend loaded but no USB devices found")
        print("   (This might be normal if no USB devices are connected)")
    else:
        print("   ✅ Backend is working - USB devices detected")
except usb.core.NoBackendError:
    print("   ❌ NO BACKEND FOUND!")
    print("\n   Windows needs libusb-1.0.dll")
    print("\n   Solutions:")
    print("   1. Install libusb using: pip install libusb")
    print("   2. Or download libusb manually:")
    print("      - Download from: https://github.com/libusb/libusb/releases")
    print("      - Extract libusb-1.0.dll to:")
    print(f"        {sys.prefix}\\DLLs\\")
    print("      - Or to: C:\\Windows\\System32\\")
except Exception as e:
    print(f"   ❌ Error checking backend: {e}")

print("\n3. Checking Python environment...")
print(f"   Python: {sys.version}")
print(f"   Prefix: {sys.prefix}")
print(f"   Executable: {sys.executable}")

# Check if running in venv
if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    print("   Environment: Virtual environment (venv)")
else:
    print("   Environment: System Python")

print("\n" + "=" * 70)
print("RECOMMENDED FIX:")
print("=" * 70)
print("\nRun this command to install libusb:")
print("   pip install libusb")
print("\nOr install libusb-package:")
print("   pip install libusb-package")
print("\n" + "=" * 70)
