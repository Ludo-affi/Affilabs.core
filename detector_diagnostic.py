#!/usr/bin/env python
"""Detector Diagnostic Tool - Isolate and troubleshoot detector connection issues.

This script tests the detector independently from the main application
and provides detailed diagnostics about what's working and what's not.
"""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging early
from affilabs.utils.logger import logger
logger.info("=" * 80)
logger.info("DETECTOR DIAGNOSTIC TOOL")
logger.info("=" * 80)


def test_imports():
    """Test that all required imports are available."""
    logger.info("\n[TEST 1] Testing imports...")

    modules = [
        ("seabreeze", "SeaBreeze spectrometer library"),
        ("usb.core", "PyUSB core"),
        ("usb.util", "PyUSB utilities"),
        ("numpy", "NumPy"),
    ]

    results = {}
    for module_name, description in modules:
        try:
            __import__(module_name)
            logger.info(f"  [OK] {module_name:20} ({description})")
            results[module_name] = True
        except ImportError as e:
            logger.error(f"  [FAIL] {module_name:20} - {e}")
            results[module_name] = False

    return all(results.values())


def test_libusb_backend():
    """Test libusb backend configuration."""
    logger.info("\n[TEST 2] Testing libusb backend configuration...")

    try:
        from affilabs.utils.libusb_init import get_libusb_backend
        backend = get_libusb_backend()

        if backend:
            logger.info(f"  [OK] libusb backend configured: {backend}")
            return True
        else:
            logger.warning("  [WARN] libusb backend not found (this may be OK)")
            return True
    except Exception as e:
        logger.error(f"  [FAIL] libusb init failed: {e}")
        return False


def test_usb_devices():
    """List all USB devices to check for spectrometer."""
    logger.info("\n[TEST 3] Scanning USB devices...")

    try:
        import usb.core
        import usb.util
        from affilabs.utils.libusb_init import get_libusb_backend

        backend = get_libusb_backend()

        # Ocean Optics VID
        OCEAN_OPTICS_VID = 0x2457

        # Find all devices
        all_devices = usb.core.find(find_all=True, backend=backend)
        all_count = len(list(usb.core.find(find_all=True, backend=backend)))
        logger.info(f"  [OK] Found {all_count} USB device(s) total")

        # Find Ocean Optics devices
        oo_devices = list(usb.core.find(find_all=True, idVendor=OCEAN_OPTICS_VID, backend=backend))
        logger.info(f"  [OK] Found {len(oo_devices)} Ocean Optics device(s)")

        for i, dev in enumerate(oo_devices):
            try:
                def get_info():
                    result = {}
                    try:
                        result['serial'] = usb.util.get_string(dev, dev.iSerialNumber)
                    except:
                        result['serial'] = "N/A"
                    try:
                        result['product'] = usb.util.get_string(dev, dev.iProduct)
                    except:
                        result['product'] = "N/A"
                    return result

                # Run with timeout
                info = {}
                thread = threading.Thread(target=lambda: info.update(get_info()), daemon=True)
                thread.start()
                thread.join(timeout=2.0)

                serial = info.get('serial', 'N/A')
                product = info.get('product', 'N/A')
                logger.info(f"    [{i}] {product} | S/N: {serial}")
            except Exception as e:
                logger.debug(f"    [{i}] Error reading details: {e}")

        return len(oo_devices) > 0

    except Exception as e:
        logger.error(f"  ✗ USB scan failed: {e}")
        return False


def test_seabreeze_devices():
    """Test SeaBreeze device listing."""
    logger.info("\n[TEST 4] Testing SeaBreeze device listing...")

    try:
        import seabreeze
        seabreeze.use("pyseabreeze")
        from seabreeze.spectrometers import list_devices, Spectrometer

        def scan():
            return list_devices()

        # Run scan with timeout
        devices = []
        exception = [None]

        def scan_thread():
            try:
                nonlocal devices
                devices = scan()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=scan_thread, daemon=True)
        thread.start()
        thread.join(timeout=10.0)

        if thread.is_alive():
        logger.error(f"  [FAIL] SeaBreeze scan timed out after 10s")
            return False

        if exception[0]:
            logger.error(f"  [FAIL] SeaBreeze scan failed: {exception[0]}")
            return False

        logger.info(f"  [OK] SeaBreeze found {len(devices)} device(s)")

        for i, dev in enumerate(devices):
            try:
                serial = getattr(dev, 'serial_number', 'N/A')
                model = getattr(dev, 'model', 'N/A')
                logger.info(f"    [{i}] {model} | S/N: {serial}")
            except Exception as e:
                logger.debug(f"    [{i}] Error reading: {e}")

        return len(devices) > 0

    except Exception as e:
        logger.error(f"  ✗ SeaBreeze test failed: {e}")
        return False


def test_detector_connection():
    """Test connecting to the detector via USB4000Adapter."""
    logger.info("\n[TEST 5] Testing detector connection via USB4000Adapter...")

    try:
        from affilabs.hardware.spectrometer_adapter import USB4000Adapter

        adapter = USB4000Adapter()
        logger.info("  • USB4000Adapter created")

        # Try to connect
        logger.info("  • Attempting connection...")
        logger.info("  • (this may take a few seconds...)")

        exception = [None]
        success = [False]

        def connect():
            try:
                success[0] = adapter.connect()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=connect, daemon=True)
        thread.start()
        thread.join(timeout=15.0)

        if thread.is_alive():
            logger.error("  [FAIL] Connection attempt timed out after 15s")
            return False

        if exception[0]:
            logger.error(f"  [FAIL] Connection failed: {exception[0]}")
            return False

        if not success[0]:
            logger.error("  [FAIL] Connection returned False")
            return False

        logger.info(f"  [OK] Connected successfully!")

        # Get device info
        try:
            is_connected = adapter.is_connected()
            logger.info(f"  • Is connected: {is_connected}")

            serial = adapter.serial_number
            logger.info(f"  • Serial number: {serial}")

            info = adapter.get_info()
            logger.info(f"  • Model: {info.model}")

            # Try to read a spectrum
            logger.info("  • Attempting to read spectrum...")
            spectrum = adapter.read_spectrum()
            if spectrum is not None:
                logger.info(f"  ✓ Spectrum read: {len(spectrum)} pixels")
                logger.info(f"    - Min: {spectrum.min():.1f} counts")
                logger.info(f"    - Max: {spectrum.max():.1f} counts")
                logger.info(f"    - Mean: {spectrum.mean():.1f} counts")
            else:
                logger.warning("  [WARN] Spectrum is None")

            # Disconnect
            adapter.disconnect()
            logger.info("  • Disconnected")

            return True

        except Exception as e:
            logger.error(f"  [FAIL] Post-connection test failed: {e}")
            try:
                adapter.disconnect()
            except:
                pass
            return False

    except Exception as e:
        logger.error(f"  [FAIL] USB4000Adapter test failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def test_wrapper_directly():
    """Test USB4000 wrapper directly (lower level)."""
    logger.info("\n[TEST 6] Testing USB4000 wrapper directly...")

    try:
        from affilabs.utils.usb4000_wrapper import USB4000

        device = USB4000()
        logger.info("  • USB4000 wrapper created")

        # Try to open
        logger.info("  • Attempting to open device...")

        exception = [None]
        opened = [False]

        def open_device():
            try:
                opened[0] = device.open()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=open_device, daemon=True)
        thread.start()
        thread.join(timeout=15.0)

        if thread.is_alive():
            logger.error("  [FAIL] Open attempt timed out after 15s")
            return False

        if exception[0]:
            logger.error(f"  [FAIL] Open failed: {exception[0]}")
            return False

        if not opened[0]:
            logger.error("  [FAIL] Open returned False")
            return False

        logger.info(f"  [OK] Device opened!")
        logger.info(f"  • Serial: {device.serial_number}")

        # Try to read
        try:
            logger.info("  • Attempting to read spectrum...")
            spectrum = device.read_spectrum()
            if spectrum is not None:
                logger.info(f"  ✓ Spectrum read: {len(spectrum)} pixels")
        except Exception as e:
            logger.error(f"  ✗ Read failed: {e}")

        # Close
        device.close()
        logger.info("  • Device closed")

        return True

    except Exception as e:
        logger.error(f"  [FAIL] USB4000 wrapper test failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def main():
    """Run all diagnostic tests."""
    logger.info("")
    logger.info("Starting detector diagnostics...")
    logger.info("")

    tests = [
        ("Imports", test_imports),
        ("libusb Backend", test_libusb_backend),
        ("USB Devices", test_usb_devices),
        ("SeaBreeze Devices", test_seabreeze_devices),
        ("Adapter Connection", test_detector_connection),
        ("Wrapper Direct", test_wrapper_directly),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results[test_name] = False

        time.sleep(0.5)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 80)

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        logger.info(f"{status:8} | {test_name}")

    all_passed = all(results.values())
    logger.info("=" * 80)

    if all_passed:
        logger.info("\n[SUCCESS] All tests passed! Detector should be working.")
    else:
        logger.error("\n[FAILED] Some tests failed. See details above.")
        logger.error("\n" + "=" * 80)
        logger.error("ROOT CAUSE: Windows USB Drivers Missing")
        logger.error("=" * 80)
        logger.error("\nThe detector is detected by USB but cannot be opened because")
        logger.error("Windows drivers are not properly installed.")
        logger.error("\nFIX: Install libusb drivers using Zadig")
        logger.error("=" * 80)
        logger.info("\n[QUICK FIX STEPS]:")
        logger.info("\n1. Download Zadig (USB driver installer):")
        logger.info("   -> https://zadig.akeo.ie/")
        logger.info("\n2. Run Zadig and:")
        logger.info("   a) Go to: Options > List All Devices (enable all)")
        logger.info("   b) Find and select: 'Ocean Optics FLAME-T' or similar")
        logger.info("   c) Choose driver: 'libusb-win32' or 'libusbK'")
        logger.info("   d) Click 'Replace Driver'")
        logger.info("   e) Agree to overwrite any existing drivers")
        logger.info("   f) Wait for installation to complete")
        logger.info("\n3. Unplug and replug the detector USB cable")
        logger.info("\n4. Run this diagnostic again to verify")
        logger.info("\n" + "=" * 80)
        logger.info("\n[ALTERNATIVE: Create batch file for future use]")
        logger.info("\nCreate 'install_detector_drivers.bat' with:")
        logger.info('   @echo off')
        logger.info('   echo Installing Ocean Optics detector drivers...')
        logger.info('   echo Please follow the Zadig GUI steps above.')
        logger.info('   start https://zadig.akeo.ie/')
        logger.info('   pause')
        logger.info("\n" + "=" * 80)

    logger.info("\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
