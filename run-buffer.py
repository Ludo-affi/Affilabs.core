#!/usr/bin/env python3
"""Run Buffer Through System - Continuous Flow Operation

Runs continuous buffer flow through the fluidic system using full 1mL cycles.
Aspirates 1000µL from inlet, dispenses through flow cell, repeats for specified
duration or number of cycles at a set flow rate.

Usage:
    python run-buffer.py                           # Default: 10 cycles @ 50µL/min
    python run-buffer.py --cycles 20               # 20 cycles
    python run-buffer.py --duration 30             # Run for 30 minutes
    python run-buffer.py --flow-rate 100           # 100 µL/min flow rate
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


async def run_buffer_cycles(
    pump,
    cycles: int = None,
    duration_minutes: float = None,
    flow_rate_ul_min: float = 50.0,
) -> bool:
    """Run buffer through system with full 1mL cycles.
    
    Args:
        pump: PumpHAL instance
        cycles: Number of cycles (if specified, takes priority over duration)
        duration_minutes: Duration in minutes (used if cycles not specified)
        flow_rate_ul_min: Flow rate in µL/min
    
    Returns:
        True if successful
    """
    global _shutdown_requested
    
    # Determine mode
    if cycles is not None:
        mode = "cycles"
        logger.info(f"\n🔄 Running Buffer: {cycles} cycles @ {flow_rate_ul_min} µL/min")
    else:
        mode = "duration"
        if duration_minutes is None:
            duration_minutes = 10.0  # Default
        total_volume_needed = flow_rate_ul_min * duration_minutes
        estimated_cycles = int(total_volume_needed / 1000.0) + 1
        logger.info(f"\n🔄 Running Buffer: {duration_minutes} minutes @ {flow_rate_ul_min} µL/min")
        logger.info(f"   Estimated cycles: {estimated_cycles} (1000µL each)")
        cycles = estimated_cycles
    
    flow_rate_ul_s = flow_rate_ul_min / 60.0
    
    start_time = time.time()
    total_volume = 0.0
    cycle_count = 0
    
    for cycle in range(1, cycles + 1):
        if _shutdown_requested:
            logger.info(f"\n⚠️  Stopped after {cycle_count} cycles")
            break
        
        # Check duration limit if in duration mode
        if mode == "duration":
            elapsed_minutes = (time.time() - start_time) / 60.0
            if elapsed_minutes >= duration_minutes:
                logger.info(f"\n✅ Duration target reached: {elapsed_minutes:.1f} minutes")
                break
        
        cycle_count = cycle
        logger.info(f"\n  Cycle {cycle}/{cycles}:")
        
        # Aspirate 1000µL from inlet
        logger.info(f"    → Aspirating 1000µL from INLET...")
        pump._pump.pump.aspirate_both(1000.0, flow_rate_ul_s)
        
        p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            120.0  # 2 minute timeout for slow flow rates
        )
        
        if not (p1_ready and p2_ready):
            logger.error("❌ Aspirate failed")
            if not p1_ready:
                logger.error("   → Pump 1 (KC1) failed")
            if not p2_ready:
                logger.error("   → Pump 2 (KC2) failed")
            return False
        
        logger.info(f"    ✓ Aspirated in {elapsed:.1f}s")
        
        await asyncio.sleep(0.2)
        
        # Dispense 1000µL through flow cell (OUTPUT)
        logger.info(f"    → Dispensing 1000µL through OUTPUT...")
        pump._pump.pump.dispense_both(1000.0, flow_rate_ul_s)
        
        p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            120.0
        )
        
        if not (p1_ready and p2_ready):
            logger.error("❌ Dispense failed")
            if not p1_ready:
                logger.error("   → Pump 1 (KC1) failed")
            if not p2_ready:
                logger.error("   → Pump 2 (KC2) failed")
            return False
        
        logger.info(f"    ✓ Dispensed in {elapsed:.1f}s")
        
        # Update totals
        total_volume += 1000.0  # Each cycle delivers 1000µL
        
        # Progress report
        elapsed_total = (time.time() - start_time) / 60.0
        logger.info(f"    📊 Progress: {total_volume:.0f}µL delivered, {elapsed_total:.1f} min elapsed")
        
        await asyncio.sleep(0.2)
    
    # Final summary
    elapsed_total = (time.time() - start_time) / 60.0
    logger.info("\n" + "=" * 70)
    logger.info("✅ BUFFER RUN COMPLETED")
    logger.info(f"   Cycles: {cycle_count}")
    logger.info(f"   Volume delivered: {total_volume:.0f}µL")
    logger.info(f"   Time elapsed: {elapsed_total:.1f} minutes")
    logger.info(f"   Average flow rate: {total_volume / elapsed_total:.1f} µL/min")
    logger.info("=" * 70)
    
    return True


async def run_buffer_operation(
    cycles: int = None,
    duration_minutes: float = None,
    flow_rate_ul_min: float = 50.0,
) -> bool:
    """Main buffer running function.
    
    Args:
        cycles: Number of cycles (takes priority if specified)
        duration_minutes: Duration in minutes
        flow_rate_ul_min: Flow rate in µL/min
    
    Returns:
        True if successful
    """
    from affilabs.core.hardware_manager import HardwareManager
    
    logger.info("=" * 70)
    logger.info("BUFFER RUN - CONTINUOUS FLOW OPERATION")
    logger.info("=" * 70)
    
    if cycles is not None:
        logger.info(f"Mode: {cycles} cycles @ {flow_rate_ul_min} µL/min")
    else:
        logger.info(f"Mode: {duration_minutes} minutes @ {flow_rate_ul_min} µL/min")
    
    logger.info("=" * 70)
    
    # Connect to hardware
    logger.info("\n=== Connecting to Pump ===")
    hm = HardwareManager()
    
    try:
        hm._connect_pump()
        
        if not hm.pump:
            logger.error("❌ No pump found")
            return False
        
        logger.info("✅ Pump connected successfully")
        
        # Initialize pumps
        logger.info("\n=== Initializing Pumps ===")
        hm.pump.initialize_pumps()
        p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            hm.pump._pump.pump.wait_until_both_ready,
            30.0
        )
        
        if not (p1_ready and p2_ready):
            logger.error("Pump initialization failed")
            return False
        
        logger.info(f"✅ Both pumps initialized in {elapsed:.1f}s")
        
        # Run buffer cycles
        success = await run_buffer_cycles(
            hm.pump,
            cycles=cycles,
            duration_minutes=duration_minutes,
            flow_rate_ul_min=flow_rate_ul_min
        )
        
        if not success:
            return False
        
        # Home plungers at end
        logger.info("\n🔧 Sending plungers to home position...")
        hm.pump.initialize_pumps()
        p1_ready, p2_ready, elapsed, p1_time, p2_time = await asyncio.get_event_loop().run_in_executor(
            None,
            hm.pump._pump.pump.wait_until_both_ready,
            30.0
        )
        
        if p1_ready and p2_ready:
            logger.info(f"✅ Plungers homed to 0µL in {elapsed:.1f}s")
        
        return True
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
        return False
    except Exception as e:
        logger.exception(f"❌ Buffer run failed: {e}")
        return False
    finally:
        # Emergency stop
        logger.info("\n🔧 Stopping pumps...")
        if hm and hm.pump:
            try:
                hm.pump._pump.pump.send_command("/0TR")
                await asyncio.sleep(0.5)
                logger.info("✅ Pumps stopped")
                
                hm.pump.close()
                logger.info("✅ Pump connection closed")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run buffer through fluidic system with continuous 1mL cycles"
    )
    
    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--cycles",
        type=int,
        help="Number of cycles to run (takes priority over duration)",
    )
    mode_group.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Duration in minutes (default: 10)",
    )
    
    # Flow rate
    parser.add_argument(
        "--flow-rate",
        type=float,
        default=50.0,
        help="Flow rate in µL/min (default: 50)",
    )
    
    args = parser.parse_args()
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run buffer operation
    success = asyncio.run(
        run_buffer_operation(
            cycles=args.cycles,
            duration_minutes=args.duration if args.cycles is None else None,
            flow_rate_ul_min=args.flow_rate,
        )
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
