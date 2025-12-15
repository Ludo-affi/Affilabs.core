"""Direct test to connect to FLAME-T using different methods."""

print("Testing FLAME-T connection methods...")
print("=" * 60)

# Method 1: Try SeaBreeze with verbose output
print("\n1. Testing SeaBreeze cseabreeze backend:")
try:
    import seabreeze

    print(f"   SeaBreeze version: {seabreeze.__version__}")
    seabreeze.use("cseabreeze")
    print("   Using cseabreeze backend")

    from seabreeze.spectrometers import Spectrometer, list_devices

    devices = list_devices()
    print(f"   Found {len(devices)} device(s)")

    if devices:
        for dev in devices:
            print("\n   Device info:")
            print(f"   - Model: {dev.model}")
            print(f"   - Serial: {dev.serial_number}")

            # Try connecting
            print("\n   Attempting connection...")
            spec = Spectrometer.from_serial_number(dev.serial_number)
            print("   ✓ Connected!")

            # Get wavelengths
            wavelengths = spec.wavelengths()
            print(
                f"   ✓ Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm",
            )

            # Get spectrum
            spec.integration_time_micros(100000)  # 100ms
            intensities = spec.intensities()
            print(f"   ✓ Spectrum acquired: {len(intensities)} pixels")

            spec.close()
    else:
        print("   ✗ No devices found")

except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback

    traceback.print_exc()

# Method 2: Try pyseabreeze backend
print("\n2. Testing SeaBreeze pyseabreeze backend:")
try:
    import seabreeze

    seabreeze.use("pyseabreeze")
    print("   Using pyseabreeze backend")

    from seabreeze.spectrometers import list_devices

    devices = list_devices()
    print(f"   Found {len(devices)} device(s)")

    if devices:
        for dev in devices:
            print(f"   - {dev.model} (Serial: {dev.serial_number})")

except Exception as e:
    print(f"   ✗ Error: {e}")

# Method 3: Check USB device directly
print("\n3. Checking raw USB device:")
try:
    import usb.core

    # Ocean Optics vendor ID: 0x2457
    # USB4000/FLAME product ID: 0x1022
    dev = usb.core.find(idVendor=0x2457, idProduct=0x1022)
    if dev:
        print("   ✓ Found USB device:")
        print(f"   - VID: 0x{dev.idVendor:04x}")
        print(f"   - PID: 0x{dev.idProduct:04x}")
        print(f"   - Manufacturer: {usb.util.get_string(dev, dev.iManufacturer)}")
        print(f"   - Product: {usb.util.get_string(dev, dev.iProduct)}")
        print(f"   - Serial: {usb.util.get_string(dev, dev.iSerialNumber)}")
    else:
        print("   ✗ No USB device found")
except ImportError:
    print("   pyusb not installed, skipping")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
