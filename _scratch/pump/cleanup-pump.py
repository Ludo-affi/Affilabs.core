#!/usr/bin/env python3
"""Pump Cleanup Tool - Uses PumpManager

Complete pump cleaning sequence using PumpManager.
No duplicate logic - delegates to production pump operations.

Usage:
    python cleanup-pump.py                    # Default settings
    python cleanup-pump.py --pulse-cycles 20  # More pulsing
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

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global _shutdown_requested
    logger.info("\n⚠️  Shutdown requested (Ctrl+C)")
    _shutdown_requested = True


async def run_cleanup(
    pulse_cycles: int = 10,
    pulse_volume: float = 200.0,
    pulse_speed: float = 5000.0,
) -> bool:
    """Run pump cleanup using PumpManager.cleanup_pump().

    Args:
        pulse_cycles: Number of pulsing cycles
        pulse_volume: Volume for pulsing in µL
        pulse_speed: Speed for pulsing in µL/min

    Returns:
        True if successful
    """
    global _shutdown_requested

    logger.info("=== Pump Cleanup (Using PumpManager) ===")
    logger.info(f"  Pulse cycles: {pulse_cycles}")
    logger.info(f"  Pulse volume: {pulse_volume} µL")
    logger.info(f"  Pulse speed: {pulse_speed} µL/min")

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
        if hm.ctrl:
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

        # Run cleanup using PumpManager (single source of truth)
        logger.info("\n🚀 Starting cleanup operation via PumpManager...")
        success = await pump_manager.cleanup_pump(
            pulse_cycles=pulse_cycles,
            pulse_volume=pulse_volume,
            pulse_speed=pulse_speed,
        )

        if success and not _shutdown_requested:
            logger.info("\n=== Pump Cleanup Completed Successfully ===")
        elif _shutdown_requested:
            logger.warning("\n=== Pump Cleanup Interrupted ===")
        else:
            logger.error("\n=== Pump Cleanup Failed ===")

        return success

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
        return False
    except Exception as e:
        logger.exception(f"❌ Pump cleanup failed: {e}")
        return False
    finally:
        # Cleanup handled by PumpManager
        logger.info("✅ Cleanup completed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean pump system using PumpManager"
    )

    parser.add_argument(
        "--pulse-cycles",
        type=int,
        default=10,
        help="Number of pulsing cycles (default: 10)",
    )

    parser.add_argument(
        "--pulse-volume",
        type=float,
        default=200.0,
        help="Pulse volume in µL (default: 200)",
    )

    parser.add_argument(
        "--pulse-speed",
        type=float,
        default=5000.0,
        help="Pulse speed in µL/min (default: 5000)",
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

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Run cleanup operation
    success = asyncio.run(
        run_cleanup(
            pulse_cycles=args.pulse_cycles,
            pulse_volume=args.pulse_volume,
            pulse_speed=args.pulse_speed,
        )
    )

    if _shutdown_requested:
        logger.info("\n✅ Graceful shutdown completed")
        sys.exit(130)  # Standard exit code for Ctrl+C

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
