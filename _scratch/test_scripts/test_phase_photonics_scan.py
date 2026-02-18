"""Quick test to scan for Phase Photonics detector."""

from ftd2xx import listDevices

print("=" * 80)
print("SCANNING FOR PHASE PHOTONICS DETECTOR")
print("=" * 80)

try:
    # Get all FTDI devices
    all_devices = listDevices()

    if all_devices:
        print(f"\n✓ Found {len(all_devices)} FTDI device(s):")
        for i, dev in enumerate(all_devices):
            serial = dev.decode() if isinstance(dev, bytes) else dev
            is_phase = serial.startswith("ST")
            marker = "👉 PHASE PHOTONICS!" if is_phase else ""
            print(f"  [{i}] {serial} {marker}")

        # Filter for Phase Photonics (serial starts with "ST")
        phase_devices = [s.decode() for s in all_devices if s.startswith(b"ST")]

        if phase_devices:
            print(f"\n✅ SUCCESS! Found {len(phase_devices)} Phase Photonics detector(s):")
            for dev in phase_devices:
                print(f"   - {dev}")

            # Try to connect to the first one
            print(f"\nAttempting connection to {phase_devices[0]}...")
            from pathlib import Path
            from affilabs.utils.phase_photonics_api import PhasePhotonicsAPI

            # Use Sensor.dll (64-bit version)
            dll_path = Path(__file__).parent / "affilabs" / "utils" / "Sensor64bit.dll"
            dll_name = "Sensor64bit.dll"

            print(f"Using DLL: {dll_name}")
            print(f"DLL path: {dll_path}")
            print(f"DLL exists: {dll_path.exists()}")

            if dll_path.exists():
                api = PhasePhotonicsAPI(str(dll_path))
                spec = api.usb_initialize(phase_devices[0])

                if spec:
                    print(f"✅ CONNECTED to {phase_devices[0]}!")
                    print(f"   Handle: {spec}")

                    # Try to read wavelength calibration
                    print("\nReading wavelength calibration...")
                    bytes_read, config = api.usb_read_config(spec, 0)
                    print(f"   Config bytes read: {bytes_read}")

                    # Cleanup
                    api.usb_deinit(spec)
                    print("   Disconnected")
                else:
                    print("❌ Failed to initialize detector")
            else:
                print(f"❌ DLL not found at {dll_path}")
        else:
            print("\n❌ NO Phase Photonics detectors found")
            print("   Phase Photonics devices have serials starting with 'ST'")
    else:
        print("\n❌ No FTDI devices found at all")
        print("   Check USB connection and drivers")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
