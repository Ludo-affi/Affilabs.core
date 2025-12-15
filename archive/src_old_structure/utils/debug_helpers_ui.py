"""Debug helper functions for UI testing and development.

This module contains debug/test functions that can be used during development
to test various aspects of the application without requiring full hardware setup.

Debug Shortcuts:
- Ctrl+Shift+C: Bypass calibration (mark system as calibrated)
- Ctrl+Shift+S: Start simulation mode (inject fake SPR data)
- Ctrl+Shift+1: Single data point test (minimal test)

These functions should NOT be used in production environments.
"""

from utils.logger import logger


def debug_bypass_calibration(app):
    """Debug: Mark system as calibrated without running hardware calibration (Ctrl+Shift+C).

    This is a lightweight bypass that:
    1. Marks the data manager as calibrated
    2. Injects minimal fake calibration data
    3. Enables the Start button and UI controls

    NO hardware interaction - pure UI state change for debugging.

    Args:
        app: Application instance with access to data_mgr and main_window

    """
    try:
        from utils.debug_helpers import (
            inject_fake_calibration,
            save_fake_calibration_to_config,
        )

        logger.info("=" * 80)
        logger.info("🔧 DEBUG BYPASS: Marking system as calibrated (NO HARDWARE)")
        logger.info("=" * 80)

        # Inject minimal fake calibration data into data manager
        inject_fake_calibration(app.data_mgr)

        # Save LED intensities to device config so Settings dialog shows correct values
        save_fake_calibration_to_config(app.main_window.device_config)

        # Enable Start button in UI
        if hasattr(app.main_window, "sidebar") and hasattr(
            app.main_window.sidebar,
            "start_cycle_btn",
        ):
            app.main_window.sidebar.start_cycle_btn.setEnabled(True)
            app.main_window.sidebar.start_cycle_btn.setToolTip(
                "Start Live Acquisition (Debug Mode)",
            )
            logger.info("✅ Start button enabled")

        # Enable recording controls
        app.main_window.enable_controls()
        logger.info("✅ Recording controls enabled")

        # Show success message
        from widgets.message import show_message

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
        logger.info("✅ BYPASS COMPLETE - Press Start to test UI")
        logger.info("=" * 80)

    except Exception as e:
        logger.exception(f"❌ Failed to bypass calibration: {e}")
        from widgets.message import show_message

        show_message(
            f"Failed to bypass calibration:\n{e}",
            msg_type="Error",
            title="Bypass Failed",
        )


def debug_single_data_point(app):
    """Debug: Emit a single test data point (Ctrl+Shift+1).

    Minimal test - just ONE data point, no loops, no timers.
    This isolates whether the crash is:
    - The data processing itself (crashes immediately)
    - The rate/accumulation (doesn't crash with one point)

    Args:
        app: Application instance with access to data_mgr

    """
    import time

    logger.info("=" * 80)
    logger.info("🧪 SINGLE DATA POINT TEST (Ctrl+Shift+1)")
    logger.info("=" * 80)

    try:
        # Check if data_mgr exists
        if not hasattr(app, "data_mgr") or app.data_mgr is None:
            logger.error("❌ No data_mgr found!")
            from widgets.message import show_message

            show_message("Error: Data manager not initialized!", msg_type="Error")
            return

        logger.info("✅ Data manager found")

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
        app.data_mgr.spectrum_acquired.emit(data)

        logger.info("✅ Single data point emitted")
        logger.info("⏳ Waiting 2 seconds to see if crash occurs...")

        # Use QTimer to check status after delay
        from PySide6.QtCore import QTimer

        def check_status():
            logger.info("=" * 80)
            logger.info("✅ SUCCESS - No crash after 2 seconds!")
            logger.info("   Single data point was processed successfully.")
            logger.info("   This means the crash is likely rate/accumulation related.")
            logger.info("=" * 80)
            from widgets.message import show_message

            show_message(
                "Single Data Point Test: SUCCESS!\n\n"
                "✅ No crash detected\n"
                "✅ Data processing works\n\n"
                "The crash is likely caused by:\n"
                "- High data rate overwhelming Qt\n"
                "- Event queue flooding\n"
                "- Accumulated state issues",
                msg_type="Info",
            )

        QTimer.singleShot(2000, check_status)

    except Exception as e:
        logger.exception(f"❌ Single data point test failed: {e}")
        from widgets.message import show_message

        show_message(f"Single data point test FAILED:\n\n{e}", msg_type="Error")


def debug_start_simulation(app):
    """Debug: Start injecting simulated spectra (Ctrl+Shift+S).

    Injects fake SPR spectra at 2 Hz continuously to test the complete
    data pipeline: acquisition → processing → recording → UI.

    Args:
        app: Application instance with access to data_mgr

    """
    import time

    import numpy as np
    from PySide6.QtCore import QTimer

    logger.info("=" * 80)
    logger.info("🎬 SIMULATION MODE ACTIVATED (Ctrl+Shift+S)")
    logger.info("=" * 80)

    try:
        # Check if data_mgr exists
        if not hasattr(app, "data_mgr") or app.data_mgr is None:
            logger.error("❌ No data_mgr found!")
            from widgets.message import show_message

            show_message(
                "Error: Data manager not initialized!\n\n"
                "Make sure the app has fully loaded.",
                msg_type="Error",
            )
            return

        logger.info(f"✅ Data manager found: {app.data_mgr}")

        # Check if acquisition is running
        if hasattr(app.data_mgr, "_acquiring") and not app.data_mgr._acquiring:
            logger.warning(
                "⚠️ Acquisition not running - simulation works best with acquisition active",
            )
            logger.warning("   Press Ctrl+Shift+C then click Start first")

        # Create timer to inject spectra at SLOW rate (2 Hz to prevent Qt flooding)
        timer = QTimer()
        timer.setInterval(500)  # 500ms = 2 Hz (much slower, safer)

        spectrum_count = [0]  # Use list for mutable counter
        start_time = [time.time()]  # Simulation start time

        def send_one():
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
                    transmission_spectrum = (raw_spectrum / s_ref) * 100.0  # Percentage
                    transmission_spectrum = np.clip(transmission_spectrum, 0, 150)

                    # Create data dict with full spectrum arrays (matching real format)
                    data = {
                        "channel": ch,
                        "wavelength": float(
                            peak_wavelength,
                        ),  # Resonance peak for timeline
                        "intensity": float(intensities[ch]),  # Average intensity
                        "raw_spectrum": raw_spectrum,  # Full raw spectrum array
                        "full_spectrum": raw_spectrum,  # Alias for compatibility
                        "transmission_spectrum": transmission_spectrum,  # Full transmission array
                        "wavelengths": wavelengths,  # Wavelength array for plots
                        "timestamp": time.time(),
                        "elapsed_time": elapsed,
                        "is_preview": False,
                        "simulated": True,
                    }

                    # Emit to spectrum_acquired signal
                    if app.data_mgr and hasattr(app.data_mgr, "spectrum_acquired"):
                        app.data_mgr.spectrum_acquired.emit(data)

                spectrum_count[0] += 1

                # Log every 50 cycles (5 seconds)
                if spectrum_count[0] % 50 == 0:
                    logger.info(
                        f"📊 Injected {spectrum_count[0]} simulated data cycles ({spectrum_count[0] * 4} points)",
                    )

            except Exception as e:
                logger.exception(f"❌ Simulation error: {e}")
                timer.stop()

        timer.timeout.connect(send_one)
        timer.start()

        # Store timer reference to prevent garbage collection
        app._sim_timer = timer

        logger.info("✅ Simulation timer started at 2 Hz")
        logger.info("   Generating 4 channels (A, B, C, D) per cycle")

        from widgets.message import show_message

        show_message(
            "Simulation started!\n\n"
            "📡 Sending fake SPR data at 2 Hz\n"
            "   (4 channels per cycle)\n\n"
            "Check logs to see injection status.\n"
            "Watch the graph for updates!\n\n"
            "Close the app to stop.",
            msg_type="Info",
        )

    except Exception as e:
        logger.exception(f"❌ Failed to start simulation: {e}")
        from widgets.message import show_message

        show_message(
            f"Simulation failed:\n\n{e}",
            msg_type="Error",
        )


# Unused debug functions (kept for reference, not connected to UI)
# These can be removed entirely if never needed


def debug_simulate_calibration_success(app):
    """Force a simulated successful calibration (debug/testing only).

    DEPRECATED: Use debug_bypass_calibration() instead.
    This function is redundant and kept only for backward compatibility.

    Args:
        app: Application instance with access to data_mgr

    """
    try:
        from utils.debug_helpers import inject_fake_calibration

        if getattr(app.data_mgr, "calibrated", False):
            logger.info("🧪 Debug: system already calibrated; skipping simulation")
            return

        logger.info("🧪 Debug: simulating calibration success (no hardware checks)")
        inject_fake_calibration(app.data_mgr)

        # Override with lighter settings for simulation
        app.data_mgr.integration_time = 36
        app.data_mgr.num_scans = 1
        app.data_mgr.p_mode_intensity = {"a": 180, "b": 180, "c": 180, "d": 180}
        app.data_mgr.s_mode_intensity = {"a": 180, "b": 180, "c": 180, "d": 180}

        logger.info("🧪 Debug: calibration bypassed (no signal emitted)")
    except Exception as e:
        logger.error(f"🧪 Debug: calibration simulation failed: {e}")


def debug_test_acquisition_thread(app):
    """Debug: Test acquisition worker thread without calibration.

    DEPRECATED: This test function is no longer needed in production.
    Kept for reference only.

    Args:
        app: Application instance with access to hardware_mgr and data_mgr

    """
    try:
        from utils.debug_helpers import create_mock_hardware, inject_fake_calibration

        logger.info("🧪 DEBUG: Testing acquisition thread (no hardware needed)")

        # Create mock hardware if not connected
        create_mock_hardware(app.hardware_mgr)

        # Inject minimal fake calibration data into data manager
        inject_fake_calibration(app.data_mgr)
        logger.info("🧪 DEBUG: Fake calibration data injected")

        # Now start acquisition - this should trigger the Qt threading error if it exists
        app.data_mgr.start_acquisition()
        logger.info("🧪 DEBUG: Acquisition started - watch for Qt threading errors")
        logger.info("🧪 DEBUG: If app crashes now, it's the Qt threading bug")

    except Exception as e:
        logger.error(f"🧪 DEBUG: Thread test failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
