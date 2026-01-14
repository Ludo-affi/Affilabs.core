"""Resource Management Helper Utilities.

Provides helper functions for:
- Application cleanup and shutdown
- Hardware disconnection
- Thread termination
- Resource release

These are utility functions extracted from the main Application class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
                print("Stopping processing thread...")
                app._stop_processing_thread()

                # Stop data acquisition
                if app.data_mgr:
                    print("Stopping data acquisition...")
                    try:
                        app.data_mgr.stop_acquisition()
                    except Exception as e:
                        print(f"Error stopping data acquisition: {e}")

                # Stop recording
                if app.recording_mgr and app.recording_mgr.is_recording:
                    print("Stopping recording...")
                    try:
                        app.recording_mgr.stop_recording()
                    except Exception as e:
                        print(f"Error stopping recording: {e}")

                # Stop all pumps
                if app.kinetic_mgr:
                    print("Stopping pumps...")
                    try:
                        app.kinetic_mgr.stop_all_pumps()
                    except Exception as e:
                        print(f"Error stopping pumps: {e}")

                # Home pumps to zero position before closing
                if hasattr(app, "hardware_mgr") and app.hardware_mgr:
                    if hasattr(app.hardware_mgr, "pump") and app.hardware_mgr.pump:
                        print("Homing pumps to zero position...")
                        try:
                            import asyncio
                            # Run async home_pumps in sync context
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(app.hardware_mgr.pump.home_pumps())
                            loop.close()
                            print("✓ Pumps homed successfully")
                        except Exception as e:
                            print(f"Error homing pumps: {e}")

            # Disconnect hardware (force close in emergency mode)
            if hasattr(app, "hardware_mgr") and app.hardware_mgr:
                if not emergency:
                    print("Disconnecting hardware...")
                try:
                    # Close controller
                    if (
                        hasattr(app.hardware_mgr, "controller")
                        and app.hardware_mgr.controller
                    ):
                        try:
                            if not emergency:
                                app.hardware_mgr.controller.stop()
                            app.hardware_mgr.controller.close()
                        except Exception as e:
                            if not emergency:
                                print(f"Error closing controller: {e}")

                    # Close spectrometer
                    if (
                        hasattr(app.hardware_mgr, "spectrometer")
                        and app.hardware_mgr.spectrometer
                    ):
                        try:
                            app.hardware_mgr.spectrometer.close()
                        except Exception as e:
                            if not emergency:
                                print(f"Error closing spectrometer: {e}")
                except Exception as e:
                    if not emergency:
                        print(f"Error during hardware disconnect: {e}")

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
                            print(f"Error closing kinetics: {e}")

            if not emergency:
                # Avoid arbitrary sleeps; threads joined above.
                print("[OK] Application closed successfully")
            else:
                print("[OK] Emergency cleanup completed")

        except Exception as e:
            if not emergency:
                print(f"Error during cleanup: {e}")
