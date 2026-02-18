"""Test script for the new inject_with_valve_timing function.

This script demonstrates how to use the inject function that:
1. Loads pump at default aspiration flowrate
2. Dispenses at assay flowrate (from sidebar)
3. Opens 6-port valves 15 seconds after dispense starts
4. Calculates contact time based on loop volume / flowrate
5. Closes valves after contact time
6. Continues dispensing until empty (single cycle, no refill)

Usage:
    python test_inject_function.py
"""

import asyncio
import sys

from affilabs.utils.logger import logger


async def test_inject():
    """Test the inject_with_valve_timing function."""
    logger.info("="*60)
    logger.info("Testing inject_with_valve_timing function")
    logger.info("="*60)

    # Import required modules
    try:
        from affilabs.core.hardware_manager import HardwareManager
        from affilabs.managers.pump_manager import PumpManager
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        return False

    # Create hardware manager
    logger.info("\n1. Initializing hardware manager...")
    hw_manager = HardwareManager()

    # Wait for hardware initialization
    await asyncio.sleep(2)

    if not hw_manager.pump:
        logger.error("❌ No pump hardware detected!")
        logger.info("Please ensure:")
        logger.info("  - AffiPump is powered on")
        logger.info("  - USB cable is connected")
        logger.info("  - FTDI drivers are installed")
        return False

    logger.info("✓ Pump hardware detected")

    # Create pump manager
    logger.info("\n2. Creating pump manager...")
    pump_mgr = PumpManager(hw_manager)
    logger.info("✓ Pump manager created")

    # Test parameters
    logger.info("\n3. Test parameters:")
    assay_flow_rate = 15.0  # µL/min (from sidebar assay setting)
    aspiration_flow_rate = 24000.0  # µL/min (default)
    loop_volume = 100.0  # µL
    valve_open_delay = 15.0  # seconds
    pulse_rate = 1200.0  # µL/min (KC2 spike rate - configurable in advanced settings)

    logger.info(f"   Assay flow rate: {assay_flow_rate} µL/min")
    logger.info(f"   Aspiration flow rate: {aspiration_flow_rate} µL/min")
    logger.info(f"   Loop volume: {loop_volume} µL")
    logger.info(f"   Valve open delay: {valve_open_delay}s")
    logger.info(f"   Pulse rate: {pulse_rate} µL/min")

    # Calculate expected contact time
    contact_time = (loop_volume / assay_flow_rate) * 60.0
    logger.info(f"   Expected contact time: {contact_time:.2f}s")

    # Run inject sequence
    logger.info("\n4. Starting inject sequence...")
    success = await pump_mgr.inject_with_valve_timing(
        assay_flow_rate=assay_flow_rate,
        aspiration_flow_rate=aspiration_flow_rate,
        loop_volume_ul=loop_volume,
        valve_open_delay_s=valve_open_delay,
        pulse_rate=pulse_rate,
    )

    if success:
        logger.info("\n✅ Inject sequence completed successfully!")
    else:
        logger.error("\n❌ Inject sequence failed!")

    return success


async def main():
    """Main entry point."""
    try:
        success = await test_inject()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the async test
    asyncio.run(main())
