#!/usr/bin/env python
"""Detector Diagnostic Tool - Isolate and troubleshoot detector connection issues."""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging early
from affilabs.utils.logger import logger

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


def test_usb_devices():
    """List all USB devices to check for spectrometer."""
    logger.info("\n[TEST 2] Scanning USB devices...")

    try:
        import usb.core
        from affilabs.utils.libusb_init import get_libusb_backend

        backend = get_libusb_backend()
        OCEAN_OPTICS_VID = 0x2457

        # Count all devices
        all_count = len(list(usb.core.find(find_all=True, backend=backend)))
        logger.info(f"  [OK] Found {all_count} USB device(s) total")

        # Find Ocean Optics devices
        oo_devices = list(usb.core.find(find_all=True, idVendor=OCEAN_OPTICS_VID, backend=backend))
        logger.info(f"  [OK] Found {len(oo_devices)} Ocean Optics device(s)")

        for i, dev in enumerate(oo_devices):
            logger.info(f"    [{i}] VID=0x{dev.idVendor:04x} PID=0x{dev.idProduct:04x}")

        return len(oo_devices) > 0

    except Exception as e:
        logger.error(f"  [FAIL] USB scan failed: {e}")
        return False


def test_seabreeze_devices():
    """Test SeaBreeze device listing."""
    logger.info("\n[TEST 3] Testing SeaBreeze device listing...")

    try:
        import seabreeze
        seabreeze.use("pyseabreeze")
        from seabreeze.spectrometers import list_devices

        devices = []
        exception = [None]

        def scan_thread():
            try:
                nonlocal devices
                devices = list_devices()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=scan_thread, daemon=True)
        thread.start()
        thread.join(timeout=10.0)

        if thread.is_alive():
            logger.error("  [FAIL] SeaBreeze scan timed out after 10s")
            return False

        if exception[0]:
            logger.error(f"  [FAIL] SeaBreeze scan failed: {exception[0]}")
            return False

        logger.info(f"  [OK] SeaBreeze found {len(devices)} device(s)")
        return len(devices) > 0

    except Exception as e:
        logger.error(f"  [FAIL] SeaBreeze test failed: {e}")
        return False


def test_detector_connection():
    """Test connecting to the detector via USB4000Adapter."""
    logger.info("\n[TEST 4] Testing detector connection via USB4000Adapter...")

    try:
        from affilabs.hardware.spectrometer_adapter import USB4000Adapter

        adapter = USB4000Adapter()
        logger.info("  Opening detector connection (may take a few seconds)...")

        success = [False]

        def connect():
            try:
                success[0] = adapter.connect()
            except Exception:
                pass

        thread = threading.Thread(target=connect, daemon=True)
        thread.start()
        thread.join(timeout=15.0)

        if thread.is_alive():
            logger.error("  [FAIL] Connection attempt timed out after 15s")
            return False

        if not success[0]:
            logger.error("  [FAIL] Connection returned False")
            return False

        logger.info(f"  [OK] Connected successfully!")
        adapter.disconnect()
        return True

    except Exception as e:
        logger.error(f"  [FAIL] USB4000Adapter test failed: {e}")
        return False


def main():
    """Run all diagnostic tests."""
    logger.info("\n" + "=" * 80)
    logger.info("DETECTOR DIAGNOSTIC TOOL")
    logger.info("=" * 80)
    logger.info("")

    tests = [
        ("Imports", test_imports),
        ("USB Devices", test_usb_devices),
        ("SeaBreeze Devices", test_seabreeze_devices),
        ("Adapter Connection", test_detector_connection),
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
        logger.info("\n[SUCCESS] All tests passed! Detector is working properly.")
    else:
        logger.error("\n[FAILED] Some tests failed. ROOT CAUSE ANALYSIS below:\n")
        logger.error("ROOT CAUSE: Windows USB Drivers Missing")
        logger.error("=" * 80)
        logger.error("\nThe detector is detected by USB but cannot be opened because")
        logger.error("Windows drivers are not properly installed.\n")
        logger.error("FIX: Install libusb drivers using Zadig (USB driver tool)")
        logger.error("=" * 80)
        logger.info("\n[QUICK FIX STEPS]:\n")
        logger.info("1. Download Zadig from: https://zadig.akeo.ie/\n")
        logger.info("2. Run Zadig and follow these steps:")
        logger.info("   a) Go to: Options > List All Devices")
        logger.info("   b) Look for: 'Ocean Optics FLAME-T' or 'FLAME' in the list")
        logger.info("   c) Select the libusb driver from dropdown (libusb-win32 or libusbK)")
        logger.info("   d) Click 'Replace Driver'")
        logger.info("   e) Wait for installation to complete")
        logger.info("   f) Click OK when done\n")
        logger.info("3. IMPORTANT: Unplug and replug the detector USB cable\n")
        logger.info("4. Run this diagnostic again to verify:\n")
        logger.info("   python detector_diagnostic_simple.py\n")
        logger.error("=" * 80)

    logger.info("\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
