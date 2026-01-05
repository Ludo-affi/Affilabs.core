#!/usr/bin/env python3
"""Pump Cleanup Tool - Standalone Cleaning Script

Complete standalone pump cleaning sequence:
1. Pulsating: Push 250µL out, pull 200µL back through OUTPUT (10x)
2. Prime Pump: Full aspirate/dispense cycles (6x) 
3. Close all valves
4. Send plungers home to 0µL

This helps remove air bubbles, particles, and contaminants from:
- Pump chambers
- Valves (6-port and 3-way)
- Tubing connections
- Flow cells

Usage:
    python cleanup-pump.py                    # Default settings
    python cleanup-pump.py --pulse-cycles 20  # More pulsing
    python cleanup-pump.py --fast             # High-speed cleaning
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import time

# Add affilabs to path if running as standalone script
if __name__ == "__main__":
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

from affilabs.utils.logger import logger

# Global flag for graceful shutdown
_shutdown_requested = False

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global _shutdown_requested
    logger.info("\n⚠️  Shutdown requested (Ctrl+C)")
    _shutdown_requested = True


async def _home_plungers(pump) -> bool:
    """Send plungers to home position (0µL).
    
    Args:
        pump: PumpHAL instance
    
    Returns:
        True if successful
    """
    logger.info("🏠 Sending plungers to home position for graceful exit...")
    try:
        pump.initialize_pumps()
        p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            30.0
        )
        if p1_ready and p2_ready:
            logger.info(f"✅ Plungers homed to 0µL in {elapsed:.1f}s")
            return True
        else:
            logger.warning("⚠️  Failed to home plungers")
            return False
    except Exception as e:
        logger.error(f"❌ Error homing plungers: {e}")
        return False



def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global _shutdown_requested
    if not _shutdown_requested:
        _shutdown_requested = True
        logger.info("\n⚠️  Shutdown requested (Ctrl+C). Stopping pumps safely...")
        logger.info("Please wait for cleanup to complete...")
    else:
        logger.warning("Force shutdown requested. Exiting immediately.")
        sys.exit(1)


async def pulsate_both_pumps(
    pump,
    pulse_volume: float = 200.0,
    cycles: int = 10,
    speed: float = 5000.0,
) -> bool:
    """Pulsating back-and-forth through OUTPUT port only.
    
    Starts with full syringe, keeps output valve open, and pulses:
    Push 250µL out, pull 200µL back - repeat 10x through OUTPUT only.
    
    Args:
        pump: PumpHAL instance
        pulse_volume: Volume to pull back (push is pulse_volume + 50µL)
        cycles: Number of pulse cycles
        speed: Speed in µL/min
    
    Returns:
        True if successful
    """
    global _shutdown_requested
    
    logger.info(f"\n🌊 Pulsating: {cycles} cycles (push 250µL, back {pulse_volume}µL) @ {speed} µL/min through OUTPUT")
    
    speed_ul_s = speed / 60.0
    push_volume = pulse_volume + 50.0  # Push 250, back 200 = net 50µL out
    
    # First, fill both syringes completely
    logger.info("  Filling syringes to 1000µL...")
    pump._pump.pump.aspirate_both(1000.0, speed_ul_s)
    pump1_ready, pump2_ready, elapsed, pump1_time, pump2_time = await asyncio.get_event_loop().run_in_executor(
        None,
        pump._pump.pump.wait_until_both_ready,
        60.0
    )
    
    if not (pump1_ready and pump2_ready):
        logger.error("Failed to fill syringes")
        return False
    
    await asyncio.sleep(0.2)
    
    # Set both pumps to OUTPUT and keep there
    logger.info("  Setting output valves...")
    pump._pump.pump.send_command("/1OR")
    await asyncio.sleep(0.5)
    pump._pump.pump.send_command("/2OR")
    await asyncio.sleep(0.5)
    
    for cycle in range(1, cycles + 1):
        if _shutdown_requested:
            return False
        
        logger.info(f"  Pulse {cycle}/{cycles}: PUSH {push_volume}µL → BACK {pulse_volume}µL")
        
        # Push out (dispense through output - position command only, valve stays)
        pump._pump.pump.send_command(f"/AV{int(speed_ul_s)},1R")
        await asyncio.sleep(0.1)
        steps = int(push_volume * 181.49)
        pump._pump.pump.send_command(f"/AD{steps}R")
        
        pump1_ready, pump2_ready, elapsed, pump1_time, pump2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            30.0
        )
        
        if not (pump1_ready and pump2_ready):
            logger.error("❌ Pulse push failed - one or both pumps not responding")
            if not pump1_ready:
                logger.error("   → Pump 1 (KC1) failed")
            if not pump2_ready:
                logger.error("   → Pump 2 (KC2) failed")
            return False
        
        # Check for blockage during push (time difference)
        # Blocked pump finishes FASTER, healthy pump takes LONGER
        time_diff = abs(pump1_time - pump2_time)
        if time_diff > 2.0:
            blocked_pump = "KC2" if pump1_time > pump2_time else "KC1"
            logger.error(f"❌ PUSH time difference: {time_diff:.2f}s - {blocked_pump} is BLOCKED!")
            return False  # Stop on blockage
        
        await asyncio.sleep(0.1)
        
        # Pull back (aspirate through output - position command only, valve stays)
        # Use half speed for pull back
        pull_speed_ul_s = speed_ul_s / 2.0
        pump._pump.pump.send_command(f"/AV{int(pull_speed_ul_s)},1R")
        await asyncio.sleep(0.1)
        steps = int(pulse_volume * 181.49)
        pump._pump.pump.send_command(f"/AP{steps}R")
        
        pump1_ready, pump2_ready, elapsed, pump1_time, pump2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            10.0
        )
        
        if not (pump1_ready and pump2_ready):
            logger.error("❌ Pulse back failed - one or both pumps not responding")
            if not pump1_ready:
                logger.error("   → Pump 1 (KC1) failed")
            if not pump2_ready:
                logger.error("   → Pump 2 (KC2) failed")
            return False
        
        # Check for blockage during pull (time difference)
        # Blocked pump finishes FASTER, healthy pump takes LONGER
        time_diff = abs(pump1_time - pump2_time)
        if time_diff > 1.5:
            blocked_pump = "KC2" if pump1_time > pump2_time else "KC1"
            logger.error(f"❌ PULL time difference: {time_diff:.2f}s - {blocked_pump} is BLOCKED!")
            return False  # Stop on blockage
        
        # Wait 1 second after pulling back before next push
        await asyncio.sleep(1.0)
    
    logger.info("✅ Pulsating complete")
    return True


async def seesaw_pumps(
    pump,
    ctrl,
    cycles: int = 6,
    speed: float = 5000.0,
) -> bool:
    """Prime pump sequence - aspirate/dispense cycles with valve control.
    
    Runs the full prime pump sequence with both pumps in parallel.
    Opens 6-port valves at cycle 3, 3-way valves at cycle 5.
    
    Args:
        pump: PumpHAL instance
        ctrl: Controller instance for valve control
        cycles: Number of prime cycles (default: 6)
        speed: Dispense speed in µL/min (aspirate is fixed at 24000)
    
    Returns:
        True if successful
    """
    global _shutdown_requested
    
    logger.info(f"\n⚖️  Prime Pump Sequence: {cycles} cycles × 1000µL (aspirate @ 24000, dispense @ {speed} µL/min)")
    
    aspirate_speed_ul_s = 24000.0 / 60.0
    dispense_speed_ul_s = speed / 60.0
    
    for cycle in range(1, cycles + 1):
        if _shutdown_requested:
            return False
        
        logger.info(f"  Cycle {cycle}/{cycles}...")
        
        # Valve operations at specific cycles (matching prime-pump.py)
        if ctrl:
            if cycle == 3:
                logger.info("    🔧 Opening BOTH load valves (6-port KC1 & KC2 to inject)...")
                if ctrl.knx_six_both(1):
                    logger.info("    ✅ Both 6-port valves opened")
                else:
                    logger.warning("    ⚠️  Failed to open 6-port valves")
                await asyncio.sleep(0.5)
            
            elif cycle == 5:
                logger.info("    🔧 Opening BOTH channel valves (3-way KC1 & KC2 to load)...")
                if ctrl.knx_three_both(1):
                    logger.info("    ✅ Both 3-way valves opened")
                else:
                    logger.warning("    ⚠️  Failed to open 3-way valves")
                await asyncio.sleep(0.5)
        
        # Get positions before aspirate
        pos_before = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.get_both_positions
        )
        logger.info(f"    BEFORE aspirate - Pump1: {pos_before['pump1']:.2f}µL, Pump2: {pos_before['pump2']:.2f}µL")
        
        # Aspirate both pumps (switches to INLET valves internally)
        logger.info("    → Switching pump valves to INLET...")
        logger.info("    → Both pumps ASPIRATE (1000µL)")
        pump._pump.pump.aspirate_both(1000.0, aspirate_speed_ul_s)
        
        # Wait for both
        p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            60.0
        )
        
        if not (p1_ready and p2_ready):
            logger.error("Aspirate failed")
            return False
        
        # Check for time-based blockage during aspirate
        # CRITICAL: Blocked pump finishes FASTER (can't move fluid), healthy pump takes LONGER
        time_diff = abs(p1_time - p2_time)
        if time_diff > 1.5:
            blocked_pump = "KC2" if p1_time > p2_time else "KC1"  # Faster = blocked
            logger.error(f"❌ ASPIRATE time difference: {time_diff:.2f}s - {blocked_pump} is BLOCKED!")
            return False  # Stop on blockage
        
        # Get positions after aspirate
        pos_after_asp = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.get_both_positions
        )
        logger.info(f"    AFTER aspirate - Pump1: {pos_after_asp['pump1']:.2f}µL, Pump2: {pos_after_asp['pump2']:.2f}µL")
        
        await asyncio.sleep(0.2)
        
        # Dispense both pumps (switches to OUTLET valves internally)
        logger.info("    → Switching pump valves to OUTLET...")
        logger.info("    → Both pumps DISPENSE (1000µL)")
        pump._pump.pump.dispense_both(1000.0, dispense_speed_ul_s)
        
        # Wait for both
        p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            60.0
        )
        
        if not (p1_ready and p2_ready):
            logger.error("Dispense failed")
            return False
        
        # Check for time-based blockage during dispense
        # CRITICAL: Blocked pump finishes FASTER (can't push fluid), healthy pump takes LONGER
        time_diff = abs(p1_time - p2_time)
        if time_diff > 2.0:
            blocked_pump = "KC2" if p1_time > p2_time else "KC1"  # Faster = blocked
            logger.error(f"❌ DISPENSE time difference: {time_diff:.2f}s - {blocked_pump} is BLOCKED!")
            return False  # Stop on blockage
        
        # Get positions after dispense
        pos_after_disp = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.get_both_positions
        )
        logger.info(f"    AFTER dispense - Pump1: {pos_after_disp['pump1']:.2f}µL, Pump2: {pos_after_disp['pump2']:.2f}µL")
        
        # Check for position-based blockage
        # Higher volume after dispense = didn't dispense fully = BLOCKED
        volume_diff = abs(pos_after_disp['pump1'] - pos_after_disp['pump2'])
        if volume_diff > 50.0:
            blocked_pump = "KC1" if pos_after_disp['pump1'] > pos_after_disp['pump2'] else "KC2"
            logger.error(f"❌ Volume difference: {volume_diff:.1f}µL - {blocked_pump} is BLOCKED (didn't dispense)!")
            return False  # Stop on blockage
        
        await asyncio.sleep(0.2)
    
    logger.info("✅ Prime pump sequence complete")
    return True


async def cycle_valves(ctrl, cycles: int = 3) -> bool:
    """Cycle all valves to flush connections.
    
    Opens and closes all valves to flush debris from valve seats.
    
    Args:
        ctrl: Controller instance with valve control
        cycles: Number of valve cycles
    
    Returns:
        True if successful
    """
    global _shutdown_requested
    
    if not ctrl:
        logger.warning("No controller - skipping valve cycling")
        return True
    
    logger.info(f"\n🔄 Valve Cycling: {cycles} cycles")
    
    for cycle in range(1, cycles + 1):
        if _shutdown_requested:
            return False
        
        logger.info(f"  Cycle {cycle}/{cycles}...")
        
        # Open all valves
        logger.info("    → Opening all valves")
        ctrl.knx_six_both(1)  # 6-port to inject
        await asyncio.sleep(0.5)
        ctrl.knx_three_both(1)  # 3-way to load
        await asyncio.sleep(1.0)
        
        # Close all valves
        logger.info("    → Closing all valves")
        ctrl.knx_six_both(0)  # 6-port to load
        await asyncio.sleep(0.5)
        ctrl.knx_three_both(0)  # 3-way to waste
        await asyncio.sleep(1.0)
    
    logger.info("✅ Valve cycling complete")
    return True


def _connect_hardware():
    """Connect to pump and controller hardware."""
    from affilabs.core.hardware_manager import HardwareManager

    logger.info("=== Connecting to Hardware ===")
    hm = HardwareManager()

    try:
        # Connect to pump
        logger.info("Scanning for pump...")
        hm._connect_pump()

        if not hm.pump:
            logger.error("❌ No pump found")
            return None, None

        logger.info("✅ Pump connected successfully")

        # Connect to controller for valve control
        logger.info("Scanning for controller (for valve control)...")
        hm._connect_controller()

        if not hm.ctrl:
            logger.warning("⚠️ No controller found - valve cycling will be skipped")
            return hm.pump, None

        logger.info(f"✅ Controller connected: {hm.ctrl.get_device_type()}")
        return hm.pump, hm._ctrl_raw

    except Exception as e:
        logger.exception(f"Hardware connection failed: {e}")
        return None, None


async def cleanup_system(
    pulse_volume: float = 200.0,
    pulse_cycles: int = 10,
    prime_cycles: int = 6,
    fast_mode: bool = False,
) -> bool:
    """Run complete cleanup sequence - STANDALONE.
    
    Sequence:
    1. Pulsating (push 250µL, back 200µL through OUTPUT)
    2. Prime pump sequence (full aspirate/dispense cycles)
    3. Close all valves
    4. Send plungers home to 0µL
    
    Args:
        pulse_volume: Volume to pull back (push is +50µL)
        pulse_cycles: Number of pulsating cycles
        prime_cycles: Number of prime pump cycles
        fast_mode: Use higher speeds for aggressive cleaning
    
    Returns:
        True if successful
    """
    logger.info("=" * 70)
    logger.info("FLUIDIC SYSTEM CLEANUP - STANDALONE")
    logger.info("=" * 70)
    logger.info("Configuration:")
    logger.info(f"  Pulse: {pulse_cycles} cycles (push 250µL, back {pulse_volume}µL)")
    logger.info(f"  Prime: {prime_cycles} cycles × 1000µL")
    logger.info(f"  Fast mode: {'ENABLED' if fast_mode else 'DISABLED'}")
    logger.info("=" * 70)

    # Speeds
    pulse_speed = 12000.0 if fast_mode else 5000.0
    prime_speed = 12000.0 if fast_mode else 5000.0

    # Connect to hardware
    pump, ctrl = _connect_hardware()
    if not pump:
        logger.error("❌ Cannot start cleanup without pump connection")
        return False

    try:
        # Initialize pumps
        logger.info("\n=== Initializing Pumps ===")
        pump.initialize_pumps()
        pump1_ready, pump2_ready, elapsed, pump1_time, pump2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            30.0
        )
        
        if not (pump1_ready and pump2_ready):
            logger.error("Pump initialization failed")
            return False
        
        logger.info(f"✅ Both pumps initialized in {elapsed:.1f}s")
        
        # Initial fill cycles - 3 full cycles to add liquid throughout system
        logger.info("\n🔧 Initial Fill Cycles (3× 1000µL to fill system)...")
        for cycle in range(1, 4):
            logger.info(f"  Fill cycle {cycle}/3...")
            
            # Aspirate 1000µL from inlet
            pump._pump.pump.aspirate_both(1000.0, prime_speed / 60.0)
            p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                60.0
            )
            if not (p1_ready and p2_ready):
                logger.error("Fill aspirate failed")
                return False
            
            await asyncio.sleep(0.2)
            
            # Dispense 1000µL to outlet
            pump._pump.pump.dispense_both(1000.0, prime_speed / 60.0)
            p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                60.0
            )
            if not (p1_ready and p2_ready):
                logger.error("Fill dispense failed")
                return False
            
            await asyncio.sleep(0.2)
        
        logger.info("✅ Initial fill cycles complete")

        # Phase 1: Pulsating
        if not await pulsate_both_pumps(pump, pulse_volume, pulse_cycles, pulse_speed):
            logger.error("❌ Pulsating phase 1 failed - sending plungers home before exit")
            await _home_plungers(pump)
            return False
        
        # Reinitialize pumps after pulsating to reset positions
        logger.info("\n🔧 Re-initializing pumps after pulsating...")
        pump.initialize_pumps()
        pump1_ready, pump2_ready, elapsed, pump1_time, pump2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            30.0
        )
        
        if not (pump1_ready and pump2_ready):
            logger.error("Pump re-initialization failed")
            return False
        
        logger.info(f"✅ Pumps re-initialized in {elapsed:.1f}s")

        # Phase 2: Prime pump sequence (with valve control)
        if not await seesaw_pumps(pump, ctrl, prime_cycles, prime_speed):
            logger.error("❌ Prime pump sequence failed - sending plungers home before exit")
            await _home_plungers(pump)
            return False
        
        # Phase 3: Pulsating again (after prime, before closing valves)
        logger.info("\n🔧 Pulsating again after prime pump...")
        if not await pulsate_both_pumps(pump, pulse_volume, pulse_cycles, pulse_speed):
            logger.error("❌ Pulsating phase 2 failed - sending plungers home before exit")
            await _home_plungers(pump)
            return False

        # Phase 4: Close all valves
        if ctrl:
            logger.info("\n🔧 Closing all valves (return to safe state)...")
            
            # Close 6-port valves first
            logger.info("  Closing 6-port valves (to LOAD position)...")
            ctrl.knx_six_both(0)
            await asyncio.sleep(0.5)
            
            # Monitor 6-port valve state
            try:
                six_state_1 = ctrl.knx_six_state(1)
                six_state_2 = ctrl.knx_six_state(2)
                logger.info(f"  ✓ 6-port Valve 1: {'LOAD (0)' if six_state_1 == 0 else 'INJECT (1)'}")
                logger.info(f"  ✓ 6-port Valve 2: {'LOAD (0)' if six_state_2 == 0 else 'INJECT (1)'}")
            except Exception as e:
                logger.warning(f"  ⚠️  Could not read 6-port valve state: {e}")
            
            # Close 3-way valves
            logger.info("  Closing 3-way valves...")
            ctrl.knx_three_both(0)
            await asyncio.sleep(0.5)
            
            # Monitor 3-way valve state
            try:
                three_state_1 = ctrl.knx_three_state(1)
                three_state_2 = ctrl.knx_three_state(2)
                logger.info(f"  ✓ 3-way Valve 1: {three_state_1}")
                logger.info(f"  ✓ 3-way Valve 2: {three_state_2}")
            except Exception as e:
                logger.warning(f"  ⚠️  Could not read 3-way valve state: {e}")
            
            logger.info("✅ All valves closed")
        
        # Phase 5: Pulsating one more time (after closing valves)
        logger.info("\n🔧 Final pulsating with valves closed...")
        if not await pulsate_both_pumps(pump, pulse_volume, pulse_cycles, pulse_speed):
            logger.error("❌ Final pulsating failed - sending plungers home before exit")
            await _home_plungers(pump)
            return False
        
        # Phase 6: Send plungers home
        logger.info("\n🔧 Sending plungers to home position...")
        try:
            # Initialize pumps to home plungers
            pump.initialize_pumps()
            p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                30.0
            )
            if p1_ready and p2_ready:
                logger.info(f"✅ Plungers homed to 0µL via initialization in {elapsed:.1f}s")
            else:
                logger.warning("⚠️  Failed to home plungers")
        except Exception as e:
            logger.warning(f"Failed to home plungers: {e}")

        logger.info("\n" + "=" * 70)
        logger.info("✅ CLEANUP COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)

        return True

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
        return False
    except Exception as e:
        logger.exception(f"❌ Cleanup failed: {e}")
        return False
    finally:
        # Emergency stop
        logger.info("\n🔧 Stopping pumps...")
        if pump:
            try:
                pump._pump.pump.send_command("/0TR")
                await asyncio.sleep(0.5)
                logger.info("✅ Pumps stopped")
                
                pump.close()
                logger.info("✅ Pump connection closed")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Standalone fluidic system cleanup - pulsating + prime pump sequence"
    )
    parser.add_argument(
        "--pulse-volume",
        type=float,
        default=200.0,
        help="Volume to pull back in µL (push is +50µL, default: 200)",
    )
    parser.add_argument(
        "--pulse-cycles",
        type=int,
        default=10,
        help="Number of pulsating cycles (default: 10)",
    )
    parser.add_argument(
        "--prime-cycles",
        type=int,
        default=6,
        help="Number of prime pump cycles (default: 6)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use high-speed cleaning (more aggressive)",
    )

    args = parser.parse_args()

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Run cleanup
    success = asyncio.run(
        cleanup_system(
            pulse_volume=args.pulse_volume,
            pulse_cycles=args.pulse_cycles,
            prime_cycles=args.prime_cycles,
            fast_mode=args.fast,
        )
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
