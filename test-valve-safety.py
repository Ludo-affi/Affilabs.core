#!/usr/bin/env python3
"""Test 6-port valve safety timeout feature

This script demonstrates the safety fallback mechanism:
1. Default: NO timeout (for programmatic operations with calculated contact time)
2. Manual operations: Explicit timeout for safety fallback
3. Quick test: Short timeout for testing
"""

import time
import logging
from affilabs.utils.controller import PicoEZSPR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_no_timeout_default():
    """Test default behavior: NO timeout (programmatic operation)"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Default NO timeout (programmatic operation)")
    logger.info("="*60)

    ctrl = PicoEZSPR()
    if not ctrl.open():
        logger.error("Failed to open controller")
        return

    try:
        # Turn ON valve WITHOUT timeout (default for programmatic operations)
        logger.info("Opening KC1 valve (default = NO timeout)...")
        success = ctrl.knx_six(state=1, ch=1)
        if success:
            logger.info("✓ Valve opened - will stay open until manually closed")
            logger.info("  (This is correct for prime pump, live data, calibration)")
        else:
            logger.error("✗ Failed to open valve")

        time.sleep(2)

        # Close valve manually (normal programmatic control)
        logger.info("\nClosing valve programmatically...")
        ctrl.knx_six(state=0, ch=1)
        logger.info("✓ Valve closed - no timer was active")

    finally:
        ctrl.close()


def test_safety_timeout_manual():
    """Test safety timeout for manual operations"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Safety timeout for manual operation (10s demo)")
    logger.info("="*60)

    ctrl = PicoEZSPR()
    if not ctrl.open():
        logger.error("Failed to open controller")
        return

    try:
        # Turn ON valve with safety timeout (for manual operations)
        logger.info("Opening KC2 valve with 10-second safety timeout...")
        logger.info("  (Use this for manual UI toggle, testing, etc.)")
        success = ctrl.knx_six(state=1, ch=2, timeout_seconds=10)
        if success:
            logger.info("✓ Valve opened - will auto-close in 10 seconds")
            logger.info("  Waiting for auto-shutoff...")

            # Wait for auto-shutoff to trigger
            time.sleep(12)
            logger.info("✓ Auto-shutoff should have triggered by now")
        else:
            logger.error("✗ Failed to open valve")

    finally:
        ctrl.close()


def test_no_timeout():
    """Test valve without timeout (timeout=0)"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Programmatic prime pump simulation (no timeout)")
    logger.info("="*60)

    ctrl = PicoEZSPR()
    if not ctrl.open():
        logger.error("Failed to open controller")
        return

    try:
        # Turn ON valve with NO timeout (simulating prime pump operation)
        logger.info("Simulating prime pump: Opening both valves (NO timeout)...")
        success = ctrl.knx_six_both(state=1)
        if success:
            logger.info("✓ Both valves opened - NO automatic shutoff")
            logger.info("  Valves stay open for calculated contact time")
            logger.info("  (Simulating 5-second contact time...)")
        else:
            logger.error("✗ Failed to open valves")

        # Simulate calculated contact time
        time.sleep(5)

        # Close valves programmatically after calculated time
        logger.info("\nClosing both valves after calculated contact time...")
        ctrl.knx_six_both(state=0)
        logger.info("✓ Both valves closed programmatically")

    finally:
        ctrl.close()


def test_both_valves_timeout():
    """Test both valves with safety timeout"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Both valves with 15-second safety timeout")
    logger.info("="*60)

    ctrl = PicoEZSPR()
    if not ctrl.open():
        logger.error("Failed to open controller")
        return

    try:
        # Turn ON both valves with 15-second timeout (manual operation fallback)
        logger.info("Opening BOTH valves with 15s safety timeout...")
        logger.info("  (Use for manual UI toggle, testing, etc.)")
        success = ctrl.knx_six_both(state=1, timeout_seconds=15)
        if success:
            logger.info("✓ Both valves opened - will auto-close in 15 seconds")
            logger.info("  Waiting for auto-shutoff...")

            # Wait for auto-shutoff to trigger
            time.sleep(17)
            logger.info("✓ Auto-shutoff should have triggered for both valves")
        else:
            logger.error("✗ Failed to open valves")

    finally:
        ctrl.close()


if __name__ == "__main__":
    logger.info("6-PORT VALVE SAFETY TIMEOUT TEST")
    logger.info("=" * 60)
    logger.info("This test demonstrates the safety fallback mechanism:")
    logger.info("• DEFAULT: NO timeout (for programmatic operations)")
    logger.info("• MANUAL: Explicit timeout (for manual/unknown duration)\n")

    # Run tests
    test_no_timeout_default()
    test_safety_timeout_manual()
    test_no_timeout()
    test_both_valves_timeout()

    logger.info("\n" + "="*60)
    logger.info("ALL TESTS COMPLETE")
    logger.info("="*60)
    logger.info("\nSUMMARY:")
    logger.info("• Programmatic operations: NO timeout (default)")
    logger.info("  - Prime pump, live data, calibration")
    logger.info("  - Valve stays open for calculated contact time")
    logger.info("• Manual operations: Explicit timeout (safety fallback)")
    logger.info("  - UI toggle, testing, unknown duration")
    logger.info("  - Pass timeout_seconds=300 for 5-minute safety")

