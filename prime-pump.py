#!/usr/bin/env python3
"""Pump Priming CLI Tool

Runs 6 cycles of aspirate-dispense (1000 µL each) to prime the pump system.
Default aspirate speed: 24000 µL/min
Default dispense speed: 500 µL/min

Architecture:
- Uses HardwareManager for consistent hardware access
- Follows HAL pattern (Hardware Abstraction Layer)
- Compatible with main application architecture

Usage:
    python prime-pump.py
    python prime-pump.py --pump 2
    python prime-pump.py --cycles 5 --volume 500
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


async def run_buffer_cycle_dual_pump(
    pump,
    volume_ul: float = 1000.0,
    aspirate_speed: float = 24000.0,
    dispense_speed: float = 5000.0,
) -> bool:
    """Run a single aspirate-dispense cycle on BOTH pumps in parallel.

    Uses pump status polling for efficient operation - automatically detects
    when syringe is empty/full and triggers next operation immediately.

    Args:
        pump: PumpHAL instance
        volume_ul: Volume to aspirate/dispense in µL
        aspirate_speed: Aspiration speed in µL/min
        dispense_speed: Dispense speed in µL/min

    Returns:
        True if cycle completed successfully

    """
    global _shutdown_requested
    
    try:
        if _shutdown_requested:
            return False
        
        # ============================================================
        # ASPIRATE BOTH PUMPS - SINGLE BROADCAST COMMAND
        # ============================================================
        # Log positions before
        pos_before = pump._pump.pump.get_both_positions()
        logger.info(f"Positions BEFORE aspirate: Pump1={pos_before['pump1']}, Pump2={pos_before['pump2']}")
        
        logger.info(
            f"Aspirating {volume_ul} µL at {aspirate_speed} µL/min from BOTH pumps (KC1 & KC2) - BROADCAST MODE...",
        )
        
        # Convert µL/min to µL/s
        aspirate_speed_ul_s = aspirate_speed / 60.0
        
        # Use broadcast command - starts BOTH pumps with ONE serial transaction
        start_time = time.time()
        pump._pump.pump.aspirate_both(volume_ul, aspirate_speed_ul_s)
        logger.info("  → Both pumps started SIMULTANEOUSLY via broadcast command")

        # Wait for both pumps efficiently using built-in method
        logger.info("  → Waiting for both pumps to complete...")
        timeout_s = 60.0
        pump1_ready, pump2_ready, elapsed, pump1_time, pump2_time = await asyncio.get_event_loop().run_in_executor(
            None, 
            pump._pump.pump.wait_until_both_ready,
            timeout_s
        )
        
        if not pump1_ready:
            logger.error("Pump 1 aspiration timed out")
            return False
        if not pump2_ready:
            logger.error("Pump 2 aspiration timed out")
            return False
        
        # Check for speed difference between pumps
        if pump1_time and pump2_time:
            time_diff = abs(pump1_time - pump2_time)
            slower_pump = "Pump1" if pump1_time > pump2_time else "Pump2"
            if time_diff > 0.5:  # More than 0.5s difference
                logger.warning(f"⚠️  SPEED DIFFERENCE DETECTED during aspirate!")
                logger.warning(f"   Pump1: {pump1_time:.1f}s, Pump2: {pump2_time:.1f}s (Δ {time_diff:.1f}s)")
                logger.warning(f"   {slower_pump} is slower - possible blockage or mechanical issue")
        
        logger.info(f"✅ Both pumps aspiration completed in {elapsed:.1f}s (BROADCAST SYNC)")
        
        # Small delay to let pump update position registers
        await asyncio.sleep(0.05)
        
        # Log positions after aspirate
        pos_after_asp = pump._pump.pump.get_both_positions()
        logger.info(f"Positions AFTER aspirate: Pump1={pos_after_asp['pump1']}, Pump2={pos_after_asp['pump2']}")
        
        # Check for pump performance mismatch (blockage detection)
        asp_delta1 = abs(pos_after_asp['pump1'] - pos_before['pump1'])
        asp_delta2 = abs(pos_after_asp['pump2'] - pos_before['pump2'])
        asp_diff = abs(asp_delta1 - asp_delta2)
        
        if asp_diff > 50.0:  # More than 50µL difference
            logger.warning(f"⚠️  BLOCKAGE DETECTED: Pump performance mismatch!")
            logger.warning(f"   Pump1 moved: {asp_delta1:.1f}µL, Pump2 moved: {asp_delta2:.1f}µL")
            logger.warning(f"   Difference: {asp_diff:.1f}µL")
            logger.warning(f"   → Likely blockage in {'KC1' if asp_delta1 < asp_delta2 else 'KC2'} fluidic system")
            logger.warning(f"   → Check 6-port valve, tubing, and connections")

        # Delay between aspirate and dispense to ensure pumps are ready
        await asyncio.sleep(0.2)

        # ============================================================
        # DISPENSE BOTH PUMPS - SINGLE BROADCAST COMMAND
        # ============================================================
        logger.info(
            f"Dispensing {volume_ul} µL at {dispense_speed} µL/min from BOTH pumps (KC1 & KC2) - BROADCAST MODE...",
        )
        
        # Convert µL/min to µL/s
        dispense_speed_ul_s = dispense_speed / 60.0
        
        # Use broadcast command - starts BOTH pumps with ONE serial transaction
        start_time = time.time()
        pump._pump.pump.dispense_both(volume_ul, dispense_speed_ul_s)
        logger.info("  → Both pumps started SIMULTANEOUSLY via broadcast command")

        # Wait for both pumps efficiently using built-in method
        logger.info("  → Waiting for both pumps to complete...")
        timeout_s = 180.0
        pump1_ready, pump2_ready, elapsed, pump1_time, pump2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            timeout_s
        )
        
        if not pump1_ready:
            logger.error("Pump 1 dispense timed out")
            return False
        if not pump2_ready:
            logger.error("Pump 2 dispense timed out")
            return False
        
        # Check for speed difference between pumps
        if pump1_time and pump2_time:
            time_diff = abs(pump1_time - pump2_time)
            slower_pump = "Pump1" if pump1_time > pump2_time else "Pump2"
            if time_diff > 1.0:  # More than 1s difference for dispense
                logger.warning(f"⚠️  SPEED DIFFERENCE DETECTED during dispense!")
                logger.warning(f"   Pump1: {pump1_time:.1f}s, Pump2: {pump2_time:.1f}s (Δ {time_diff:.1f}s)")
                logger.warning(f"   {slower_pump} is slower - possible blockage or backpressure issue")
        
        logger.info(f"✅ Both pumps dispense completed in {elapsed:.1f}s (BROADCAST SYNC)")
        
        # Small delay to let pump update position registers
        await asyncio.sleep(0.05)
        
        # Log positions after dispense
        pos_after_disp = pump._pump.pump.get_both_positions()
        logger.info(f"Positions AFTER dispense: Pump1={pos_after_disp['pump1']}, Pump2={pos_after_disp['pump2']}")
        
        # Check for pump performance mismatch during dispense (blockage detection)
        disp_delta1 = abs(pos_after_disp['pump1'] - pos_after_asp['pump1'])
        disp_delta2 = abs(pos_after_disp['pump2'] - pos_after_asp['pump2'])
        disp_diff = abs(disp_delta1 - disp_delta2)
        
        if disp_diff > 50.0:  # More than 50µL difference
            logger.warning(f"⚠️  BLOCKAGE DETECTED: Pump performance mismatch during dispense!")
            logger.warning(f"   Pump1 moved: {disp_delta1:.1f}µL, Pump2 moved: {disp_delta2:.1f}µL")
            logger.warning(f"   Difference: {disp_diff:.1f}µL")
            logger.warning(f"   → Likely blockage in {'KC1' if disp_delta1 < disp_delta2 else 'KC2'} fluidic system")
            logger.warning(f"   → Check 6-port valve, output tubing, and flow cell")

        logger.info("✅ Cycle completed for BOTH pumps")

        logger.info("✅ Cycle completed for BOTH pumps")
        return True

    except KeyboardInterrupt:
        logger.info("Cycle interrupted by user")
        return False
    except Exception as e:
        logger.exception(f"Error during buffer cycle: {e}")
        return False


def _connect_hardware():
    """Connect to pump and controller hardware using HardwareManager.

    Returns:
        Tuple of (pump HAL instance, controller instance) or (None, None) if connection failed

    """
    from affilabs.core.hardware_manager import HardwareManager

    logger.info("=== Connecting to Hardware ===")
    hm = HardwareManager()

    try:
        # Connect to pump
        logger.info("Scanning for pump...")
        hm._connect_pump()

        if not hm.pump:
            logger.error("❌ No pump found")
            logger.info("Check:")
            logger.info("  - FTDI driver installed")
            logger.info("  - USB cable connected")
            logger.info("  - Pump powered on")
            return None, None

        logger.info("✅ Pump connected successfully")

        # Connect to controller for valve control
        logger.info("Scanning for controller (for valve control)...")
        hm._connect_controller()

        if not hm.ctrl:
            logger.warning("⚠️ No controller found - valve control will be skipped")
            return hm.pump, None

        logger.info(f"✅ Controller connected: {hm.ctrl.get_device_type()}")
        return hm.pump, hm._ctrl_raw  # Return raw controller for knx valve methods

    except Exception as e:
        logger.exception(f"Hardware connection failed: {e}")
        return None, None


async def prime_pump(
    cycles: int = 6,
    volume_ul: float = 1000.0,
    aspirate_speed: float = 24000.0,
    dispense_speed: float = 5000.0,
    enable_post_prime_flow: bool = False,
) -> bool:
    """Prime BOTH pumps with multiple aspirate-dispense cycles in parallel.

    Priming sequence:
    - Cycles 1-2: Standard priming (both pumps & both KC in parallel)
    - Before cycle 3: Open both load valves (6-port valves for KC1 & KC2)
    - Cycles 3-4: Prime with load valves open (both pumps & both KC)
    - Before cycle 5: Open channel valves (3-way valves for KC1 & KC2)
    - Cycles 5-6: Prime with all valves open (both pumps & both KC)
    - After cycle 6 (if enabled): Close all valves, load syringes, flow at 30 µL/min

    Args:
        cycles: Number of aspirate-dispense cycles to run (should be 6)
        volume_ul: Volume per cycle in µL
        aspirate_speed: Aspiration speed in µL/min
        dispense_speed: Dispense speed in µL/min
        enable_post_prime_flow: Enable post-priming flow setup (default: False/disabled)

    Returns:
        True if priming completed successfully

    """
    logger.info("=== Dual Pump Priming Started ===")
    logger.info("Configuration:")
    logger.info("  Mode: DUAL PUMP (KC1 & KC2 in parallel)")
    logger.info(f"  Cycles: {cycles}")
    logger.info(f"  Volume: {volume_ul} µL per pump")
    logger.info(f"  Aspirate speed: {aspirate_speed} µL/min")
    logger.info(f"  Dispense speed: {dispense_speed} µL/min")
    logger.info(f"  Post-prime flow: {'ENABLED' if enable_post_prime_flow else 'DISABLED'}")

    # Connect to hardware
    pump, ctrl = _connect_hardware()
    if not pump:
        logger.error("❌ Cannot start priming without pump connection")
        return False

    try:
        # Initialize both pumps to establish zero position
        logger.info("\n=== Initializing Pumps ===")
        logger.info("Broadcasting initialize command to both pumps...")
        pump.initialize_pumps()
        
        # Poll until both pumps are ready (efficient status polling)
        logger.info("Waiting for both pumps to complete initialization...")
        pump1_ready, pump2_ready, elapsed, pump1_time, pump2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            30.0  # 30 second timeout for initialization
        )
        
        if not pump1_ready:
            logger.error("Pump 1 initialization timed out")
            return False
        if not pump2_ready:
            logger.error("Pump 2 initialization timed out")
            return False
        
        # Check initialization time difference
        if pump1_time and pump2_time:
            time_diff = abs(pump1_time - pump2_time)
            if time_diff > 1.0:
                logger.warning(f"⚠️  Initialization time difference: {time_diff:.1f}s")
                logger.warning(f"   Pump1: {pump1_time:.1f}s, Pump2: {pump2_time:.1f}s")
        
        logger.info(f"✅ Both pumps initialized to zero position in {elapsed:.1f}s")
        
        # Run priming cycles with valve control
        for cycle in range(1, cycles + 1):
            if _shutdown_requested:
                logger.warning("Priming interrupted by user")
                break

            # Valve operations at specific cycles
            if ctrl:
                if cycle == 3:
                    logger.info("Opening BOTH load valves (6-port KC1 & KC2 to inject)...")
                    if ctrl.knx_six_both(1):
                        logger.info("✅ Both 6-port valves opened simultaneously")
                    else:
                        logger.warning("⚠️ Failed to open 6-port valves")
                    await asyncio.sleep(0.5)  # Let valves settle
                
                elif cycle == 5:
                    logger.info("Opening BOTH channel valves (3-way KC1 & KC2 to load)...")
                    if ctrl.knx_three_both(1):
                        logger.info("✅ Both 3-way valves opened simultaneously")
                    else:
                        logger.warning("⚠️ Failed to open 3-way valves")
                    await asyncio.sleep(0.5)  # Let valves settle

            # Run the cycle on BOTH pumps in parallel
            logger.info(f"\n--- Cycle {cycle}/{cycles} (DUAL PUMP) ---")
            success = await run_buffer_cycle_dual_pump(
                pump,
                volume_ul,
                aspirate_speed,
                dispense_speed,
            )
            if not success:
                logger.error(f"Cycle {cycle} failed. Stopping priming.")
                return False

        # CRITICAL: ALWAYS close valves after priming to prevent device heating
        if ctrl:
            logger.info("\n🔒 CLOSING ALL VALVES (critical safety step)...")
            try:
                # Close 3-way valves FIRST (flow path)
                logger.info("   Closing 3-way valves (KC1 & KC2 to waste)...")
                ctrl.knx_three_both(0)
                await asyncio.sleep(0.2)
                
                # Then close 6-port valves (load path)
                logger.info("   Closing 6-port valves (KC1 & KC2 to load)...")
                ctrl.knx_six_both(0)
                await asyncio.sleep(0.5)
                
                logger.info("✅ ALL VALVES CLOSED - Device safe from heating")
            except Exception as e:
                logger.error(f"❌ CRITICAL: Failed to close valves: {e}")
                logger.error("⚠️  DEVICE MAY BE HEATING! Manually power off immediately!")
        
        if not _shutdown_requested:
            logger.info("\n=== Pump Priming Completed Successfully ===")
        else:
            logger.warning("\n=== Pump Priming Interrupted ===")

        # Post-priming flow setup (disabled by default)
        if enable_post_prime_flow:
            logger.info("\n🔧 Post-Priming Flow Setup (BOTH PUMPS)...")
            if ctrl:
                try:
                    # Close all valves simultaneously
                    logger.info("Closing all valves (KC1 & KC2)...")
                    ctrl.knx_six_both(0)  # Close both 6-port valves (load)
                    await asyncio.sleep(0.1)
                    ctrl.knx_three_both(0)  # Close both 3-way valves (waste)
                    await asyncio.sleep(0.5)
                    logger.info("✅ All valves closed (KC1 & KC2)")

                    # Load BOTH syringes in parallel
                    logger.info("Loading BOTH syringes (KC1 & KC2)...")
                    if not pump.aspirate(1, volume_ul, aspirate_speed):
                        logger.error("Failed to start aspirate on pump 1")
                        return False
                    if not pump.aspirate(2, volume_ul, aspirate_speed):
                        logger.error("Failed to start aspirate on pump 2")
                        return False
                    
                    pump.wait_until_idle(1, timeout_s=60.0)
                    pump.wait_until_idle(2, timeout_s=60.0)
                    logger.info("✅ Both syringes loaded")

                    # Start flow at 30 µL/min on BOTH pumps (Setup starting flowrate)
                    logger.info("Starting flow at 30 µL/min on BOTH pumps (Setup flowrate)...")
                    if not pump.dispense(1, volume_ul, 30.0):
                        logger.error("Failed to start flow on pump 1")
                        return False
                    if not pump.dispense(2, volume_ul, 30.0):
                        logger.error("Failed to start flow on pump 2")
                        return False
                    
                    logger.info("✅ Flow started at 30 µL/min on BOTH pumps (KC1 & KC2)")
                    logger.info("   This is the starting flowrate for 'Setup'")

                except Exception as e:
                    logger.exception(f"Post-priming flow setup failed: {e}")
                    return False
            else:
                logger.warning("No controller connected - skipping post-priming flow setup")
        else:
            logger.info("\n⚠️  Post-priming flow setup is DISABLED")
            logger.info("   To enable: use --enable-post-flow flag")

        return True

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
        # Emergency stop will happen in finally block
        return False
    except Exception as e:
        logger.exception(f"❌ Pump priming failed: {e}")
        # Emergency stop will happen in finally block
        return False
    finally:
        # EMERGENCY STOP - Critical safety feature
        logger.info("\n🔧 Cleaning up...")
        if pump:
            try:
                # STOP BOTH PUMPS IMMEDIATELY using broadcast terminate
                logger.info("⚠️  EMERGENCY STOP: Halting both pumps...")
                try:
                    # Access the raw pump controller to send terminate command
                    if hasattr(pump, '_pump') and hasattr(pump._pump, 'pump'):
                        # Send broadcast terminate to address 0 (all pumps)
                        pump._pump.pump.send_command("/0TR")  # Terminate all
                        await asyncio.sleep(0.2)
                        logger.info("✅ Both pumps terminated (broadcast command)")
                    else:
                        # Fallback: terminate each pump individually
                        logger.warning("Using fallback pump stop method")
                        pump._pump.pump.send_command("/1TR")  # Terminate pump 1
                        pump._pump.pump.send_command("/2TR")  # Terminate pump 2
                        logger.info("✅ Both pumps stopped individually")
                except Exception as e:
                    logger.error(f"❌ Failed to stop pumps: {e}")
                    logger.error("⚠️  WARNING: Pumps may still be running! Check hardware immediately!")
                
                # Small delay to let pumps respond
                await asyncio.sleep(0.5)
                
                # Close connection gracefully
                try:
                    pump.close()
                    logger.info("✅ Pump connection closed")
                except Exception as e:
                    logger.warning(f"Error closing pump connection: {e}")
                    
            except Exception as e:
                logger.error(f"❌ Critical error during cleanup: {e}")
                logger.error("⚠️  WARNING: Pumps may still be running! Manually power off if needed!")


def main():
    """Main entry point with CLI argument parsing."""
    # Install signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(
        description="Prime BOTH AffiPumps (KC1 & KC2) with aspirate-dispense cycles in parallel",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=6,
        help="Number of aspirate-dispense cycles (default: 6)",
    )
    parser.add_argument(
        "--volume",
        type=float,
        default=1000.0,
        help="Volume per cycle in µL (default: 1000)",
    )
    parser.add_argument(
        "--aspirate-speed",
        type=float,
        default=24000.0,
        help="Aspiration speed in µL/min (default: 24000)",
    )
    parser.add_argument(
        "--dispense-speed",
        type=float,
        default=5000.0,
        help="Dispense speed in µL/min (default: 5000)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--enable-post-flow",
        action="store_true",
        help="Enable post-priming flow setup (close valves, load, flow at 30 µL/min) - DISABLED by default",
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logger.setLevel("DEBUG")

    # Run priming on BOTH pumps
    try:
        success = asyncio.run(
            prime_pump(
                cycles=args.cycles,
                volume_ul=args.volume,
                aspirate_speed=args.aspirate_speed,
                dispense_speed=args.dispense_speed,
                enable_post_prime_flow=args.enable_post_flow,
            ),
        )
        
        if _shutdown_requested:
            logger.info("\n✅ Graceful shutdown completed")
            sys.exit(130)  # Standard exit code for Ctrl+C
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("\n✅ Graceful shutdown completed")
        sys.exit(130)


if __name__ == "__main__":
    main()
