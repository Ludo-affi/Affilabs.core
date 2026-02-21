"""Resource Management Helper Utilities.

Provides helper functions for:
- Application cleanup and shutdown
- Hardware disconnection
- Thread termination
- Resource release

These are utility functions extracted from the main Application class.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from main_simplified import Application  # type: ignore[import-not-found]


class ResourceHelpers:
    """Resource management utility functions.

    Static methods for cleanup and shutdown operations.
    """

    @staticmethod
    def cleanup_resources(app: Application, emergency: bool = False) -> None:
        """Consolidated cleanup logic for all shutdown paths.

        Args:
            app: Application instance
            emergency: If True, skip graceful shutdown steps and force-close hardware

        """
        try:
            if not emergency:
                # Print final profiling stats if enabled (graceful shutdown only)
                from affilabs.settings import PROFILING_ENABLED

                if PROFILING_ENABLED:
                    print("\n⚙️ FINAL PROFILING STATISTICS:")
                    app.profiler.print_stats(sort_by="total", min_calls=1)
                    app.profiler.print_hotspots(top_n=10)

                # Stop processing thread first (Phase 3)
                logger.debug("Stopping processing thread...")
                app._stop_processing_thread()

                # Stop data acquisition
                if app.data_mgr:
                    logger.debug("Stopping data acquisition...")
                    try:
                        app.data_mgr.stop_acquisition()
                    except Exception as e:
                        logger.debug(f"Error stopping data acquisition: {e}")

                # Stop recording
                if app.recording_mgr and app.recording_mgr.is_recording:
                    logger.debug("Stopping recording...")
                    try:
                        app.recording_mgr.stop_recording()
                    except Exception as e:
                        logger.debug(f"Error stopping recording: {e}")

                # Stop all pumps
                if app.kinetic_mgr:
                    logger.debug("Stopping pumps...")
                    try:
                        app.kinetic_mgr.stop_all_pumps()
                    except Exception as e:
                        logger.debug(f"Error stopping pumps: {e}")

                # Home pumps to zero position before closing
                if hasattr(app, "pump_mgr") and app.pump_mgr:
                    logger.debug("Homing pumps to zero position...")
                    try:
                        import asyncio
                        # Run async home_pumps in sync context via PumpManager
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(app.pump_mgr.home_pumps())
                        loop.close()
                        logger.debug("Pumps homed successfully")
                    except Exception as e:
                        logger.debug(f"Error homing pumps: {e}")

            # Disconnect hardware — LEDs off FIRST, then close serial/USB
            if hasattr(app, "hardware_mgr") and app.hardware_mgr:
                if not emergency:
                    logger.debug("Disconnecting hardware (LEDs off → close)...")
                try:
                    if not emergency and hasattr(app.hardware_mgr, "disconnect_all"):
                        # disconnect_all() sends 'lx' to turn all LEDs off, then closes
                        # the serial port and spectrometer in the correct order.
                        app.hardware_mgr.disconnect_all()
                    else:
                        # Emergency / fallback: use correct attribute names (ctrl, usb)
                        hw = app.hardware_mgr
                        if hasattr(hw, "ctrl") and hw.ctrl:
                            try:
                                hw.ctrl.turn_off_channels()
                            except Exception:
                                pass
                        if hasattr(hw, "_ctrl_raw") and hw._ctrl_raw:
                            try:
                                hw._ctrl_raw.close()
                            except Exception as e:
                                if not emergency:
                                    logger.debug(f"Error closing controller: {e}")
                        if hasattr(hw, "usb") and hw.usb:
                            try:
                                hw.usb.close()
                            except Exception as e:
                                if not emergency:
                                    logger.debug(f"Error closing spectrometer: {e}")
                except Exception as e:
                    if not emergency:
                        logger.debug(f"Error during hardware disconnect: {e}")

            # Close kinetics controller
            if hasattr(app, "kinetic_mgr") and app.kinetic_mgr:
                if (
                    hasattr(app.kinetic_mgr, "kinetics_controller")
                    and app.kinetic_mgr.kinetics_controller
                ):
                    try:
                        app.kinetic_mgr.kinetics_controller.close()
                    except Exception as e:
                        if not emergency:
                            logger.debug(f"Error closing kinetics: {e}")

            if not emergency:
                # Avoid arbitrary sleeps; threads joined above.
                logger.debug("Application closed successfully")
            else:
                logger.debug("Emergency cleanup completed")

        except Exception as e:
            if not emergency:
                logger.error(f"Error during cleanup: {e}")
