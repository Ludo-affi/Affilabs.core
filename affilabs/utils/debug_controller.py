"""Debug Controller for Development and Testing.

This module provides debug helpers for testing the application without hardware,
simulating calibration, injecting test data, and debugging acquisition issues.

Usage:
    from affilabs.utils.debug_controller import DebugController

    debug = DebugController(app)
    debug.bypass_calibration()
    debug.start_simulation()
"""

import logging
import time
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from main_simplified import Application

logger = logging.getLogger(__name__)


class DebugController:
    """Controller for debug and testing operations."""

    def __init__(self, app: "Application") -> None:
        """Initialize debug controller.

        Args:
            app: Application instance

        """
        self.app = app
        self.data_mgr = app.data_mgr
        self.hardware_mgr = app.hardware_mgr
        self.main_window = app.main_window
        self._sim_timer = None

    def simulate_calibration_success(self) -> None:
        """Force a simulated successful calibration (debug/testing only).

        Sets calibrated flag, populates minimal calibration data, emits calibration_complete.
        Auto-start logic (if enabled) should then begin acquisition attempt.
        """
        try:
            from affilabs.utils.debug_helpers import inject_fake_calibration

            if getattr(self.data_mgr, "calibrated", False):
                logger.info("🧪 Debug: system already calibrated; skipping simulation")
                return

            logger.info("🧪 Debug: simulating calibration success (no hardware checks)")
            inject_fake_calibration(self.data_mgr)

            # Override with lighter settings for simulation
            self.data_mgr.integration_time = 36
            self.data_mgr.num_scans = 1
            self.data_mgr.p_mode_intensity = {"a": 180, "b": 180, "c": 180, "d": 180}
            self.data_mgr.s_mode_intensity = {"a": 180, "b": 180, "c": 180, "d": 180}

            logger.info("🧪 Debug: calibration bypassed (no signal emitted)")
        except Exception as e:
            logger.exception(f"🧪 Debug: calibration simulation failed: {e}")

    def bypass_calibration(self) -> None:
        """Debug: Mark system as calibrated without running hardware calibration (Ctrl+Shift+C).

        This is a lightweight bypass that:
        1. Marks the data manager as calibrated
        2. Injects minimal fake calibration data
        3. Enables the Start button and UI controls

        NO hardware interaction - pure UI state change for debugging.
        """
        try:
            from affilabs.utils.debug_helpers import (
                inject_fake_calibration,
                save_fake_calibration_to_config,
            )

            logger.info("=" * 80)
            logger.info("🔧 DEBUG BYPASS: Marking system as calibrated (NO HARDWARE)")
            logger.info("=" * 80)

            # Inject minimal fake calibration data into data manager
            inject_fake_calibration(self.data_mgr)

            # Save LED intensities to device config so Settings dialog shows correct values
            save_fake_calibration_to_config(self.main_window.device_config)

            # Enable Start button in UI
            if hasattr(self.main_window, "sidebar") and hasattr(
                self.main_window.sidebar,
                "start_cycle_btn",
            ):
                self.main_window.sidebar.start_cycle_btn.setEnabled(True)
                self.main_window.sidebar.start_cycle_btn.setToolTip(
                    "Start Live Acquisition (Debug Mode)",
                )
                logger.info("[OK] Start button enabled")

            # Enable recording controls
            self.main_window.enable_controls()
            logger.info("[OK] Recording controls enabled")

            # Show success message
            from affilabs.widgets.message import show_message

            show_message(
                "Debug calibration bypass active!\n\n"
                "• System marked as calibrated\n"
                "• Start button enabled\n"
                "• Recording controls enabled\n\n"
                "Press 'Start' to test UI without hardware.",
                msg_type="Info",
                title="Calibration Bypassed (Debug)",
            )

            logger.info("=" * 80)
            logger.info("[OK] BYPASS COMPLETE - Press Start to test UI")
            logger.info("=" * 80)

        except Exception as e:
            logger.exception(f"[ERROR] Failed to bypass calibration: {e}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Failed to bypass calibration:\n{e}",
                msg_type="Error",
                title="Bypass Failed",
            )

    def send_single_data_point(self) -> None:
        """Debug: Emit a single test data point (Ctrl+Shift+1).

        Minimal test - just ONE data point, no loops, no timers.
        This isolates whether the crash is:
        - The data processing itself (crashes immediately)
        - The rate/accumulation (doesn't crash with one point)
        """
        logger.info("=" * 80)
        logger.info("🧪 SINGLE DATA POINT TEST (Ctrl+Shift+1)")
        logger.info("=" * 80)

        try:
            # Check if data_mgr exists
            if not self.data_mgr:
                logger.error("[ERROR] No data_mgr found!")
                from affilabs.widgets.message import show_message

                show_message("Error: Data manager not initialized!", msg_type="Error")
                return

            logger.info("[OK] Data manager found")

            # Create a single data point
            data = {
                "channel": "a",
                "wavelength": 650.0,
                "intensity": 15000.0,
                "timestamp": time.time(),
                "is_preview": False,
                "simulated": True,
            }

            logger.info(f"📤 Emitting single data point: {data}")

            # Emit to spectrum_acquired signal
            self.data_mgr.spectrum_acquired.emit(data)

            logger.info("[OK] Single data point emitted")
            logger.info("⏳ Waiting 2 seconds to see if crash occurs...")

            # Use QTimer to check status after delay
            from PySide6.QtCore import QTimer

            def check_status() -> None:
                logger.info("=" * 80)
                logger.info("[OK] SUCCESS - No crash after 2 seconds!")
                logger.info("   Single data point was processed successfully.")
                logger.info(
                    "   This means the crash is likely rate/accumulation related.",
                )
                logger.info("=" * 80)
                from affilabs.widgets.message import show_message

                show_message(
                    "Single Data Point Test: SUCCESS!\n\n"
                    "[OK] No crash detected\n"
                    "[OK] Data processing works\n\n"
                    "The crash is likely caused by:\n"
                    "- High data rate overwhelming Qt\n"
                    "- Event queue flooding\n"
                    "- Accumulated state issues",
                    msg_type="Info",
                )

            QTimer.singleShot(2000, check_status)

        except Exception as e:
            logger.exception(f"[ERROR] Single data point test failed: {e}")
            from affilabs.widgets.message import show_message

            show_message(f"Single data point test FAILED:\n\n{e}", msg_type="Error")

    def start_simulation(self) -> None:
        """Debug: Start injecting simulated spectra (Ctrl+Shift+S).

        Injects fake SPR spectra at 10 Hz continuously to test the complete
        data pipeline: acquisition → processing → recording → UI.
        """
        from PySide6.QtCore import QTimer

        logger.info("=" * 80)
        logger.info("🎬 SIMULATION MODE ACTIVATED (Ctrl+Shift+S)")
        logger.info("=" * 80)

        try:
            # Check if data_mgr exists
            if not self.data_mgr:
                logger.error("[ERROR] No data_mgr found!")
                from affilabs.widgets.message import show_message

                show_message(
                    "Error: Data manager not initialized!\n\n"
                    "Make sure the app has fully loaded.",
                    msg_type="Error",
                )
                return

            logger.info(f"[OK] Data manager found: {self.data_mgr}")

            # Check if acquisition is running
            if hasattr(self.data_mgr, "_acquiring") and not self.data_mgr._acquiring:
                logger.warning(
                    "[WARN] Acquisition not running - simulation works best with acquisition active",
                )
                logger.warning("   Press Ctrl+Shift+C then click Start first")

            # Create timer to inject spectra at SLOW rate (2 Hz to prevent Qt flooding)
            timer = QTimer()
            timer.setInterval(500)  # 500ms = 2 Hz (much slower, safer)

            spectrum_count = [0]  # Use list for mutable counter
            start_time = [time.time()]  # Simulation start time

            def send_one() -> None:
                try:
                    # Generate fake SPR wavelength data for each channel
                    channels = ["a", "b", "c", "d"]
                    peak_positions = {"a": 650, "b": 660, "c": 655, "d": 670}
                    intensities = {"a": 15000, "b": 12000, "c": 10000, "d": 14000}

                    elapsed = time.time() - start_time[0]

                    # Generate wavelength array (match real detector: ~640-690nm range for SPR)
                    wavelengths = np.linspace(
                        640,
                        690,
                        512,
                    )  # 512 points for smooth spectrum

                    for ch in channels:
                        # Generate realistic SPR peak wavelength with drift
                        base_wavelength = peak_positions[ch]
                        drift = 0.5 * np.sin(elapsed / 10)  # Slow oscillation
                        noise = np.random.normal(0, 0.1)
                        peak_wavelength = base_wavelength + drift + noise

                        # Generate full spectrum arrays (simulate SPR dip)
                        # Raw spectrum: Gaussian dip around resonance wavelength
                        raw_spectrum = intensities[ch] - 5000 * np.exp(
                            -((wavelengths - peak_wavelength) ** 2) / (2 * 3**2),
                        )
                        raw_spectrum += np.random.normal(
                            0,
                            200,
                            len(wavelengths),
                        )  # Add noise
                        raw_spectrum = np.clip(
                            raw_spectrum,
                            1000,
                            65000,
                        )  # Realistic detector range

                        # Transmission spectrum: Calculate from raw (simulate P/S ratio)
                        # Assume S_ref is constant baseline
                        s_ref = intensities[ch] * np.ones_like(wavelengths)
                        transmission_spectrum = (
                            raw_spectrum / s_ref
                        ) * 100.0  # Percentage
                        transmission_spectrum = np.clip(transmission_spectrum, 0, 150)

                        # Create data dict with full spectrum arrays (matching real format)
                        data = {
                            "channel": ch,
                            "wavelength": float(
                                peak_wavelength,
                            ),  # Resonance peak for timeline
                            "intensity": float(intensities[ch]),  # Average intensity
                            "raw_spectrum": raw_spectrum,  # Full raw spectrum array (standard field name)
                            "full_spectrum": raw_spectrum,  # DEPRECATED: Legacy alias, use raw_spectrum
                            "transmission_spectrum": transmission_spectrum,  # Full transmission array
                            "wavelengths": wavelengths,  # Wavelength array for plots
                            "timestamp": time.time(),
                            "elapsed_time": elapsed,
                            "is_preview": False,
                            "simulated": True,
                        }

                        # Emit to spectrum_acquired signal
                        if self.data_mgr and hasattr(
                            self.data_mgr,
                            "spectrum_acquired",
                        ):
                            self.data_mgr.spectrum_acquired.emit(data)

                    spectrum_count[0] += 1

                    # Log every 50 cycles (5 seconds)
                    if spectrum_count[0] % 50 == 0:
                        logger.info(
                            f"📊 Injected {spectrum_count[0]} simulated data cycles ({spectrum_count[0] * 4} points)",
                        )

                except Exception as e:
                    logger.exception(f"[ERROR] Simulation error: {e}")
                    timer.stop()

            timer.timeout.connect(send_one)
            timer.start()

            # Store timer reference to prevent garbage collection
            self._sim_timer = timer

            logger.info("[OK] Simulation timer started at 10 Hz")
            logger.info("   Generating 4 channels (A, B, C, D) per cycle")

            from affilabs.widgets.message import show_message

            show_message(
                "Simulation started!\n\n"
                "📡 Sending fake SPR data at 10 Hz\n"
                "   (4 channels per cycle)\n\n"
                "Check logs to see injection status.\n"
                "Watch the graph for updates!\n\n"
                "Close the app to stop.",
                msg_type="Info",
            )

        except Exception as e:
            logger.exception(f"[ERROR] Failed to start simulation: {e}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Simulation failed:\n\n{e}",
                msg_type="Error",
            )

    def test_acquisition_thread(self) -> None:
        """Debug: Test acquisition worker thread without calibration (Ctrl+Shift+T).

        This bypasses all hardware calibration and directly creates fake calibration
        data to test if the acquisition worker thread crashes with Qt threading errors.
        Works WITHOUT hardware connected - creates mock hardware objects.
        """
        try:
            from affilabs.utils.debug_helpers import (
                create_mock_hardware,
                inject_fake_calibration,
            )

            logger.info("🧪 DEBUG: Testing acquisition thread (no hardware needed)")

            # Create mock hardware if not connected
            create_mock_hardware(self.hardware_mgr)

            # Inject minimal fake calibration data into data manager
            inject_fake_calibration(self.data_mgr)
            logger.info("🧪 DEBUG: Fake calibration data injected")

            # Now start acquisition - this should trigger the Qt threading error if it exists
            self.data_mgr.start_acquisition()
            logger.info("🧪 DEBUG: Acquisition started - watch for Qt threading errors")

        except Exception as e:
            logger.exception(f"🧪 DEBUG: Acquisition thread test failed: {e}")
