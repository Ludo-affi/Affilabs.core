"""Test pyseabreeze backend which might work better with libusb0."""

print("Testing pyseabreeze backend (pure Python)...")
print("=" * 60)

try:
    # Must call seabreeze.use() before any imports
    import seabreeze
    seabreeze.use('pyseabreeze')
    print(f"SeaBreeze version: {seabreeze.__version__}")
    print("Using pyseabreeze backend (pure Python)")

    from seabreeze.spectrometers import list_devices, Spectrometer

    print("\nScanning for devices...")
    devices = list_devices()
    print(f"Found {len(devices)} device(s)")

    if devices:
        for i, dev in enumerate(devices):
            print(f"\nDevice {i+1}:")
            print(f"  Model: {dev.model}")
            print(f"  Serial: {dev.serial_number}")

            # Try connecting
            print(f"\n  Attempting connection...")
            spec = Spectrometer.from_serial_number(dev.serial_number)
            print(f"  ✓ Connected!")

            # Get info
            wavelengths = spec.wavelengths()
            print(f"  ✓ Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
            print(f"  ✓ Pixels: {len(wavelengths)}")

            # Set integration time and read spectrum
            spec.integration_time_micros(100000)  # 100ms
            intensities = spec.intensities()
            print(f"  ✓ Spectrum acquired: min={intensities.min():.1f}, max={intensities.max():.1f}")

            spec.close()
            print(f"  ✓ Connection closed")

            print("\n" + "=" * 60)
            print("SUCCESS! pyseabreeze backend works!")
            print("=" * 60)
    else:
        print("\n✗ No devices found with pyseabreeze backend either")
        print("\nThis suggests:")
        print("1. The libusb0 driver may not be properly installed")
        print("2. The device may need to be unplugged/replugged")
        print("3. Try WinUSB driver instead in Zadig")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

    print("\n" + "=" * 60)
    print("TROUBLESHOOTING:")
    print("=" * 60)
    print("If you see USB errors, try:")
    print("1. Install WinUSB driver using Zadig (not libusb0)")
    print("2. Unplug and replug the FLAME-T")
    print("3. Run this script again")
