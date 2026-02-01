#!/usr/bin/env python3
"""Pump Priming CLI Tool - Uses PumpManager

Runs 6 cycles of aspirate-dispense (1000 µL each) to prime the pump system.
Default aspirate speed: 24000 µL/min
Default dispense speed: 5000 µL/min

Architecture:
- Uses PumpManager (single source of truth for pump operations)
- No code duplication - delegates to production pump logic
- Provides standalone CLI interface for emergency/testing use

Usage:
    python prime-pump.py
    python prime-pump.py --cycles 5 --volume 500
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys

# Add affilabs to path if running as standalone script
if __name__ == "__main__":
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

from affilabs.utils.logger import logger
from affilabs.core.hardware_manager import HardwareManager
from affilabs.managers.pump_manager import PumpManager

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


async def run_prime_pump(
    cycles: int = 6,
    volume_ul: float = 1000.0,
    aspirate_speed: float = 24000.0,
    dispense_speed: float = 5000.0,
) -> bool:
    """Prime BOTH pumps using PumpManager (single source of truth).

    Delegates to production PumpManager.prime_pump() method.
    No duplicate logic - uses the same code path as the main application.

    Args:
        cycles: Number of aspirate-dispense cycles (default: 6)
        volume_ul: Volume per cycle in µL (default: 1000)
        aspirate_speed: Aspiration speed in µL/min (default: 24000)
        dispense_speed: Dispense speed in µL/min (default: 5000)

    Returns:
        True if priming completed successfully
    """
    global _shutdown_requested

    logger.info("=== Pump Priming (Using PumpManager) ===")
    logger.info(f"  Cycles: {cycles}")
    logger.info(f"  Volume: {volume_ul} µL per pump")
    logger.info(f"  Aspirate: {aspirate_speed} µL/min")
    logger.info(f"  Dispense: {dispense_speed} µL/min")

    # Initialize hardware
    hm = HardwareManager()

    try:
        logger.info("\n=== Connecting to Hardware ===")
        hm._connect_pump()
        if not hm.pump:
            logger.error("❌ No pump found")
            return False
        logger.info("✅ Pump connected")

        hm._connect_controller()
        if not hm.ctrl:
            logger.warning("⚠️ No controller found - valve control will be limited")
        else:
            logger.info(f"✅ Controller connected: {hm.ctrl.get_device_type()}")

        # Create PumpManager instance
        pump_manager = PumpManager(hm)

        # Connect signal handlers for progress monitoring
        def on_progress(operation, progress, message):
            logger.info(f"  Progress: {progress}% - {message}")

        def on_error(operation, error_msg):
            logger.error(f"❌ Error: {error_msg}")

        def on_completed(operation, success):
            if success:
                logger.info(f"✅ Operation '{operation}' completed successfully")
            else:
                logger.warning(f"⚠️  Operation '{operation}' failed")

        pump_manager.operation_progress.connect(on_progress)
        pump_manager.error_occurred.connect(on_error)
        pump_manager.operation_completed.connect(on_completed)

        # Run priming using PumpManager (single source of truth)
        logger.info("\n🚀 Starting prime operation via PumpManager...")
        success = await pump_manager.prime_pump(
            cycles=cycles,
            volume_ul=volume_ul,
            aspirate_speed=aspirate_speed,
            dispense_speed=dispense_speed,
        )

        if success and not _shutdown_requested:
            logger.info("\n=== Pump Priming Completed Successfully ===")
        elif _shutdown_requested:
            logger.warning("\n=== Pump Priming Interrupted ===")
        else:
            logger.error("\n=== Pump Priming Failed ===")

        return success

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
        return False
    except Exception as e:
        logger.exception(f"❌ Pump priming failed: {e}")
        return False
    finally:
        # Cleanup handled by PumpManager
        logger.info("✅ Cleanup completed")


def main():
    """Main entry point with CLI argument parsing."""
    # Install signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(
        description="Prime BOTH AffiPumps (KC1 & KC2) using PumpManager",
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

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logger.setLevel("DEBUG")

    # Run priming via PumpManager
    try:
        success = asyncio.run(
            run_prime_pump(
                cycles=args.cycles,
                volume_ul=args.volume,
                aspirate_speed=args.aspirate_speed,
                dispense_speed=args.dispense_speed,
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
