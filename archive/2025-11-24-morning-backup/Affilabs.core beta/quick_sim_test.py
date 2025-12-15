"""Quick Simulation Test
======================
Simple script to test data pipeline with simulated spectra.

Usage:
------
1. Run the application normally: python main_simplified.py
2. In another terminal, run this script: python quick_sim_test.py
   OR press Ctrl+Shift+S in the running application

This will inject simulated spectra into the running app.
"""

import time

import numpy as np

from utils.logger import logger


# Script can be imported or run standalone
def generate_fake_spectrum():
    """Generate one fake spectrum with realistic SPR data.

    Returns:
        dict: Spectrum with channels a-d and wavelengths

    """
    # Realistic Ocean Optics USB4000 specs
    n_pixels = 3648
    wavelengths = np.linspace(200, 1100, n_pixels)

    # Base noise
    noise = np.random.normal(0, 50, n_pixels)

    # Channel A: Strong peak at 650nm
    peak_a = 15000 * np.exp(-((wavelengths - 650) ** 2) / (2 * 20**2))
    channel_a = peak_a + noise + 1000

    # Channel B: Moderate peak at 660nm
    peak_b = 12000 * np.exp(-((wavelengths - 660) ** 2) / (2 * 22**2))
    channel_b = peak_b + noise + 800

    # Channel C: Weak peak at 655nm
    peak_c = 10000 * np.exp(-((wavelengths - 655) ** 2) / (2 * 18**2))
    channel_c = peak_c + noise + 900

    # Channel D: Strong peak at 670nm
    peak_d = 14000 * np.exp(-((wavelengths - 670) ** 2) / (2 * 25**2))
    channel_d = peak_d + noise + 1100

    return {
        "wavelengths": wavelengths.astype(np.float32),
        "channel_a": channel_a.astype(np.float32),
        "channel_b": channel_b.astype(np.float32),
        "channel_c": channel_c.astype(np.float32),
        "channel_d": channel_d.astype(np.float32),
        "timestamp": time.time(),
        "integration_time": 40.0,
        "simulated": True,
    }


def inject_simulated_spectrum(data_mgr, count=1):
    """Inject fake spectra directly into data manager.

    Args:
        data_mgr: DataAcquisitionManager instance
        count: Number of spectra to inject

    """
    logger.info(f"📡 Injecting {count} simulated spectra...")

    for i in range(count):
        spectrum = generate_fake_spectrum()

        # Emit directly to spectrum_acquired signal
        if hasattr(data_mgr, "spectrum_acquired"):
            data_mgr.spectrum_acquired.emit(spectrum)

        if count > 1:
            time.sleep(0.1)  # 10 Hz rate

    logger.info(f"✅ Injected {count} spectra")


# Keyboard shortcut function that can be registered
def setup_simulation_shortcut(app):
    """Add Ctrl+Shift+S shortcut to inject simulated data.

    Args:
        app: AffilabsApplication instance

    """
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QKeySequence, QShortcut

    def start_continuous_simulation():
        """Start injecting spectra continuously."""
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
                    title="Simulation Failed",
                )
                return

            logger.info(f"✅ Data manager found: {app.data_mgr}")

            # Create timer to inject spectra at 10 Hz
            timer = QTimer()
            timer.setInterval(100)  # 100ms = 10 Hz

            spectrum_count = [0]  # Use list for mutable counter

            def send_one():
                try:
                    spectrum = generate_fake_spectrum()
                    if app.data_mgr and hasattr(app.data_mgr, "spectrum_acquired"):
                        app.data_mgr.spectrum_acquired.emit(spectrum)
                        spectrum_count[0] += 1

                        # Log every 50 spectra (5 seconds)
                        if spectrum_count[0] % 50 == 0:
                            logger.info(
                                f"📊 Injected {spectrum_count[0]} simulated spectra",
                            )
                    else:
                        logger.error("❌ No spectrum_acquired signal!")
                        timer.stop()
                except Exception as e:
                    logger.exception(f"❌ Simulation error: {e}")
                    timer.stop()

            timer.timeout.connect(send_one)
            timer.start()

            # Store timer reference to prevent garbage collection
            app._sim_timer = timer

            logger.info("✅ Simulation timer started at 10 Hz")

            from widgets.message import show_message

            show_message(
                "Simulation started!\n\n"
                "📡 Sending fake spectra at 10 Hz\n\n"
                "Check logs to see injection status.\n"
                "Close the app to stop.",
                msg_type="Info",
                title="Simulation Active",
            )

        except Exception as e:
            logger.exception(f"❌ Failed to start simulation: {e}")
            from widgets.message import show_message

            show_message(
                f"Simulation failed:\n\n{e}",
                msg_type="Error",
                title="Simulation Error",
            )

    # Register Ctrl+Shift+S
    try:
        shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), app.main_window)
        shortcut.activated.connect(start_continuous_simulation)
        logger.info("⌨️ Simulation shortcut registered: Ctrl+Shift+S")
        logger.info("   Press Ctrl+Shift+S anytime to inject fake spectra")
    except Exception as e:
        logger.exception(f"❌ Failed to register simulation shortcut: {e}")


if __name__ == "__main__":
    print("This module should be imported or used via keyboard shortcut.")
    print("Press Ctrl+Shift+S in the running application to start simulation.")
