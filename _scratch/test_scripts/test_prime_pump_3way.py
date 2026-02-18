"""Test prime pump with 3-way valve diagnostic logging."""

import asyncio
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s :: %(levelname)s :: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

async def test_prime_pump():
    """Test prime pump with 3-way valve commands."""

    logger.info("=" * 80)
    logger.info("PRIME PUMP 3-WAY VALVE TEST")
    logger.info("=" * 80)

    # Initialize hardware
    from affilabs.core.hardware_manager import HardwareManager

    logger.info("🔌 Initializing hardware...")
    hardware_mgr = HardwareManager()

    # Scan for devices
    logger.info("🔍 Scanning for devices...")
    hardware_mgr.scan_devices()

    # Wait for hardware to initialize
    await asyncio.sleep(3)

    if not hardware_mgr.ctrl:
        logger.error("❌ No controller detected - cannot test 3-way valves")
        return False

    if not hardware_mgr.pump:
        logger.error("❌ No pump detected - cannot run prime pump")
        return False

    logger.info(f"✓ Controller detected: {hardware_mgr.ctrl.get_device_type()}")
    logger.info("✓ Pump detected")

    # Test individual 3-way valve commands first
    logger.info("\n" + "=" * 80)
    logger.info("TESTING INDIVIDUAL 3-WAY VALVE COMMANDS")
    logger.info("=" * 80)

    ctrl = hardware_mgr.ctrl

    logger.info("\n🔧 Test 1: Opening 3-way valve CH1 (v311)...")
    result_ch1 = ctrl.knx_three(state=1, ch=1)
    logger.info(f"   Result: {'SUCCESS' if result_ch1 else 'FAILED'}")
    await asyncio.sleep(0.5)

    logger.info("\n🔧 Test 2: Opening 3-way valve CH2 (v321)...")
    result_ch2 = ctrl.knx_three(state=1, ch=2)
    logger.info(f"   Result: {'SUCCESS' if result_ch2 else 'FAILED'}")
    await asyncio.sleep(0.5)

    logger.info("\n🔧 Test 3: Closing 3-way valve CH1 (v310)...")
    result_ch1_close = ctrl.knx_three(state=0, ch=1)
    logger.info(f"   Result: {'SUCCESS' if result_ch1_close else 'FAILED'}")
    await asyncio.sleep(0.5)

    logger.info("\n🔧 Test 4: Closing 3-way valve CH2 (v320)...")
    result_ch2_close = ctrl.knx_three(state=0, ch=2)
    logger.info(f"   Result: {'SUCCESS' if result_ch2_close else 'FAILED'}")
    await asyncio.sleep(0.5)

    if not all([result_ch1, result_ch2, result_ch1_close, result_ch2_close]):
        logger.error("\n❌ 3-WAY VALVE COMMANDS FAILED")
        logger.error("   The P4PRO firmware may not support v31/v32 commands")
        logger.error("   or the valves are not connected properly")
        return False

    logger.info("\n✅ All 3-way valve commands succeeded!")

    # Now run full prime pump sequence
    logger.info("\n" + "=" * 80)
    logger.info("RUNNING FULL PRIME PUMP SEQUENCE")
    logger.info("=" * 80)

    from affilabs.managers.pump_manager import PumpManager

    pump_mgr = PumpManager(hardware_mgr=hardware_mgr)

    logger.info("\n🚀 Starting prime pump (6 cycles)...")
    logger.info("   Watch for cycle 5 - this is where 3-way valves should open")

    success = await pump_mgr.prime_pump()

    if success:
        logger.info("\n" + "=" * 80)
        logger.info("✅ PRIME PUMP COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
    else:
        logger.error("\n" + "=" * 80)
        logger.error("❌ PRIME PUMP FAILED")
        logger.error("=" * 80)

    return success

if __name__ == "__main__":
    try:
        result = asyncio.run(test_prime_pump())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ Test failed with exception: {e}")
        sys.exit(1)
