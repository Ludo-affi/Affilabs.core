#!/usr/bin/env python3
"""Run Buffer Through System - Uses PumpManager

Runs continuous buffer flow through the fluidic system using PumpManager.
No duplicate logic - delegates to production pump operations.

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


async def run_buffer_operation(
    cycles: int = None,
    duration_minutes: float = None,
    flow_rate_ul_min: float = 50.0,
) -> bool:
    """Run buffer through system using PumpManager.run_buffer().

    Args:
        cycles: Number of cycles (takes priority if specified)
        duration_minutes: Duration in minutes
        flow_rate_ul_min: Flow rate in µL/min

    Returns:
        True if successful
    """
    global _shutdown_requested

    logger.info("=== Buffer Run (Using PumpManager) ===")
    if cycles is not None:
        logger.info(f"  Mode: {cycles} cycles @ {flow_rate_ul_min} µL/min")
    else:
        logger.info(f"  Mode: {duration_minutes} minutes @ {flow_rate_ul_min} µL/min")

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

        # Run buffer using PumpManager (single source of truth)
        logger.info("\n🚀 Starting buffer operation via PumpManager...")
        success = await pump_manager.run_buffer(
            cycles=cycles,
            duration_minutes=duration_minutes,
            flow_rate=flow_rate_ul_min,
        )

        if success and not _shutdown_requested:
            logger.info("\n=== Buffer Run Completed Successfully ===")
        elif _shutdown_requested:
            logger.warning("\n=== Buffer Run Interrupted ===")
        else:
            logger.error("\n=== Buffer Run Failed ===")

        return success

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
        return False
    except Exception as e:
        logger.exception(f"❌ Buffer run failed: {e}")
        return False
    finally:
        # Cleanup handled by PumpManager
        logger.info("✅ Cleanup completed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run buffer through fluidic system using PumpManager"
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

    # Run buffer operation
    success = asyncio.run(
        run_buffer_operation(
            cycles=args.cycles,
            duration_minutes=args.duration if args.cycles is None else None,
            flow_rate_ul_min=args.flow_rate,
        )
    )

    if _shutdown_requested:
        logger.info("\n✅ Graceful shutdown completed")
        sys.exit(130)  # Standard exit code for Ctrl+C

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
