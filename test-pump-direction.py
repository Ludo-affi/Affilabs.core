#!/usr/bin/env python3
"""Test pump 1 inlet/outlet direction at slow speed.

This script verifies the pump valve directions are correct:
- Aspirate should pull fluid FROM the inlet port
- Dispense should push fluid TO the outlet port

Watch the fluid movement to confirm:
- During aspirate: Fluid should move FROM inlet (bottom) port INTO syringe
- During dispense: Fluid should move FROM syringe TO outlet (top) port

If fluid moves in opposite direction, valve commands are inverted.
"""

import asyncio
import os
import sys
import time

# Add affilabs to path
if __name__ == "__main__":
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

from affilabs.utils.logger import logger


def _connect_pump():
    """Connect to pump hardware."""
    from affilabs.core.hardware_manager import HardwareManager

    logger.info("=== Connecting to Pump ===")
    hm = HardwareManager()

    try:
        hm._connect_pump()
        if not hm.pump:
            logger.error("❌ No pump found")
            return None
        logger.info("✅ Pump connected")
        return hm.pump
    except Exception as e:
        logger.exception(f"Connection failed: {e}")
        return None


async def test_pump_direction():
    """Test pump 1 direction at slow speed."""
    logger.info("\n" + "=" * 70)
    logger.info("PUMP 1 DIRECTION TEST - SLOW SPEED")
    logger.info("=" * 70)
    logger.info("This test will:")
    logger.info("  1. Aspirate 500µL at 1000 µL/min (SLOW)")
    logger.info("     → Should pull FROM INLET port (bottom)")
    logger.info("  2. Wait 5 seconds")
    logger.info("  3. Dispense 500µL at 1000 µL/min (SLOW)")
    logger.info("     → Should push TO OUTLET port (top)")
    logger.info("")
    logger.info("WATCH THE FLUID MOVEMENT:")
    logger.info("  - Aspirate: Inlet → Syringe (fluid pulled in from bottom)")
    logger.info("  - Dispense: Syringe → Outlet (fluid pushed out to top)")
    logger.info("=" * 70)
    logger.info("")

    pump = _connect_pump()
    if not pump:
        return False

    try:
        # Initialize pump 1
        logger.info("Initializing Pump 1...")
        pump._pump.pump.initialize_pump(1)
        await asyncio.sleep(0.5)
        
        pos = pump._pump.pump.get_both_positions()
        logger.info(f"Initial position: {pos['pump1']:.1f}µL")
        logger.info("")

        # ============================================================
        # ASPIRATE TEST - Should pull FROM INLET (bottom port)
        # ============================================================
        logger.info("=" * 70)
        logger.info("TEST 1: ASPIRATE 500µL at 1000 µL/min")
        logger.info("=" * 70)
        logger.info("Sending valve command: /1OR (to INPUT valve)")
        logger.info("Expected: Fluid should move FROM inlet port INTO syringe")
        logger.info("Watch the INLET (bottom) port now...")
        logger.info("")
        
        volume_ul = 500.0
        speed_ul_min = 1000.0
        speed_ul_s = speed_ul_min / 60.0
        
        # Send aspirate command (valve to input, then pull)
        pump._pump.pump.aspirate_both(volume_ul, speed_ul_s)
        
        # Wait for completion
        logger.info("Aspirating... (this will take ~30 seconds)")
        pump1_ready, pump2_ready, elapsed = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            60.0
        )
        
        pos = pump._pump.pump.get_both_positions()
        logger.info(f"✅ Aspirate complete in {elapsed:.1f}s")
        logger.info(f"   Position: {pos['pump1']:.1f}µL")
        logger.info("")
        logger.info("Question: Did fluid move FROM inlet (bottom) INTO syringe?")
        logger.info("  - YES: Valve direction is CORRECT")
        logger.info("  - NO: Valve direction is INVERTED")
        logger.info("")

        # Wait between operations
        logger.info("Waiting 5 seconds before dispense...")
        await asyncio.sleep(5)

        # ============================================================
        # DISPENSE TEST - Should push TO OUTLET (top port)
        # ============================================================
        logger.info("=" * 70)
        logger.info("TEST 2: DISPENSE 500µL at 1000 µL/min")
        logger.info("=" * 70)
        logger.info("Sending valve command: /1IR (to OUTPUT valve)")
        logger.info("Expected: Fluid should move FROM syringe TO outlet port")
        logger.info("Watch the OUTLET (top) port now...")
        logger.info("")
        
        # Send dispense command (valve to output, then push)
        pump._pump.pump.dispense_both(volume_ul, speed_ul_s)
        
        # Wait for completion
        logger.info("Dispensing... (this will take ~30 seconds)")
        pump1_ready, pump2_ready, elapsed = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            120.0
        )
        
        pos = pump._pump.pump.get_both_positions()
        logger.info(f"✅ Dispense complete in {elapsed:.1f}s")
        logger.info(f"   Position: {pos['pump1']:.1f}µL")
        logger.info("")
        logger.info("Question: Did fluid move FROM syringe TO outlet (top)?")
        logger.info("  - YES: Valve direction is CORRECT")
        logger.info("  - NO: Valve direction is INVERTED")
        logger.info("")

        # Summary
        logger.info("=" * 70)
        logger.info("TEST COMPLETE")
        logger.info("=" * 70)
        logger.info("If BOTH tests showed fluid moving in expected direction:")
        logger.info("  → Valve commands are CORRECT (/1OR=input, /1IR=output)")
        logger.info("")
        logger.info("If BOTH tests showed fluid moving in OPPOSITE direction:")
        logger.info("  → Valve commands are INVERTED")
        logger.info("  → Need to swap /1OR ↔ /1IR in affipump_controller.py")
        logger.info("=" * 70)

        return True

    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        logger.exception(f"❌ Test failed: {e}")
        return False
    finally:
        # Stop pump
        logger.info("\nStopping pump...")
        try:
            if pump:
                pump._pump.pump.send_command("/1TR")
                await asyncio.sleep(0.5)
                pump.close()
                logger.info("✅ Pump stopped and disconnected")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    asyncio.run(test_pump_direction())
