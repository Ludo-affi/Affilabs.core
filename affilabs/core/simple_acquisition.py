"""Simplified acquisition system - minimal version to get live data working.
Strips away all complexity and focuses on: Acquire → Process → Display.
"""

import builtins
import contextlib
import queue
import threading
import time

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from affilabs.utils.logger import logger


class SimpleAcquisitionManager(QObject):
    """Minimal acquisition manager focused on getting live data to display."""

    # Signals
    spectrum_ready = Signal(dict)  # {channel, wavelength, transmission, timestamp}
    acquisition_started = Signal()
    acquisition_stopped = Signal()
    acquisition_error = Signal(str)

    def __init__(self, hardware_mgr) -> None:
        super().__init__()
        self.hardware_mgr = hardware_mgr

        # Calibration data (set by calibration system)
        self.calibrated = False
        self.wavelengths = None
        self.dark = None
        self.s_ref = {}  # {channel: s_ref_spectrum}
        self.led_intensities = {}  # {channel: intensity}
        self.integration_time = 40

        # Acquisition state
        self._acquiring = False
        self._stop_flag = threading.Event()
        self._worker_thread = None

        # Queue for thread-safe communication
        self._data_queue = queue.Queue(maxsize=500)
        self._queue_timer = QTimer()
        self._queue_timer.timeout.connect(self._process_queue)

    def set_calibration_data(self, cal_data: dict) -> None:
        """Set calibration data from calibration system."""
        self.wavelengths = cal_data["wavelengths"]
        self.dark = cal_data["dark"]
        self.s_ref = cal_data["s_ref"]
        self.led_intensities = cal_data["led_intensities"]
        self.integration_time = cal_data.get("integration_time", 40)
        self.calibrated = True
        logger.info("[SimpleAcq] Calibration data loaded")

    def start_acquisition(self) -> None:
        """Start acquiring data."""
        if not self.calibrated:
            logger.error("[SimpleAcq] Cannot start - not calibrated")
            self.acquisition_error.emit("System not calibrated")
            return

        if self._acquiring:
            logger.warning("[SimpleAcq] Already acquiring")
            return

        logger.info("[SimpleAcq] Starting acquisition...")

        # Switch polarizer to P-mode
        try:
            ctrl = self.hardware_mgr.ctrl
            if ctrl:
                ctrl.set_mode("p")
                time.sleep(0.3)
                logger.info("[SimpleAcq] Polarizer in P-mode")
        except Exception as e:
            logger.error(f"[SimpleAcq] Failed to set polarizer: {e}")

        # Start queue processing
        self._queue_timer.start(10)

        # Start worker thread
        self._acquiring = True
        self._stop_flag.clear()
        self._worker_thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="SimpleAcqWorker",
        )
        self._worker_thread.start()

        self.acquisition_started.emit()
        logger.info("[SimpleAcq] Acquisition started")

    def stop_acquisition(self) -> None:
        """Stop acquiring data."""
        if not self._acquiring:
            return

        logger.info("[SimpleAcq] Stopping acquisition...")
        self._acquiring = False
        self._stop_flag.set()

        # Wait for worker
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

        # Stop queue timer
        self._queue_timer.stop()

        # Process remaining items
        while not self._data_queue.empty():
            try:
                self._data_queue.get_nowait()
            except queue.Empty:
                break

        self.acquisition_stopped.emit()
        logger.info("[SimpleAcq] Acquisition stopped")

    def _worker(self) -> None:
        """Worker thread - acquire and process spectra."""
        channels = ["a", "b", "c", "d"]
        cycle = 0

        try:
            while not self._stop_flag.is_set():
                cycle += 1

                # Acquire each channel
                for ch in channels:
                    if self._stop_flag.is_set():
                        break

                    try:
                        # Get spectrum
                        spectrum = self._acquire_channel(ch)

                        if spectrum is not None:
                            # Process to transmission
                            transmission = self._calc_transmission(ch, spectrum)

                            # Queue for main thread
                            data = {
                                "channel": ch,
                                "wavelength": self.wavelengths.copy(),
                                "transmission": transmission,
                                "timestamp": time.time(),
                            }

                            try:
                                self._data_queue.put_nowait(data)
                            except queue.Full:
                                pass  # Drop if queue full

                            if cycle % 10 == 1:
                                pass
                        elif cycle % 10 == 1:
                            pass

                    except Exception:
                        if cycle % 10 == 1:
                            pass

                # Small delay between cycles
                time.sleep(0.01)

        except Exception:
            with contextlib.suppress(builtins.BaseException):
                pass

    def _acquire_channel(self, channel: str):
        """Acquire spectrum for one channel."""
        try:
            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                return None

            # Turn on LED
            intensity = self.led_intensities.get(channel, 180)
            ctrl.set_intensity(ch=channel, raw_val=intensity)
            time.sleep(0.045)  # LED stabilization

            # Set integration time
            usb.set_integration(self.integration_time)

            # Read spectrum
            raw_spectrum = usb.read_intensity()

            if raw_spectrum is None:
                return None

            # Trim to match wavelengths
            if len(raw_spectrum) > len(self.wavelengths):
                raw_spectrum = raw_spectrum[: len(self.wavelengths)]

            return raw_spectrum

        except Exception:
            return None

    def _calc_transmission(self, channel: str, p_spectrum):
        """Calculate transmission: (P - dark) / (S_ref - dark)."""
        try:
            # Get S-ref for this channel
            s_ref = self.s_ref.get(channel)
            if s_ref is None:
                return None

            # Subtract dark
            p_corrected = p_spectrum - self.dark
            s_corrected = s_ref - self.dark

            # Calculate transmission
            return np.clip(p_corrected / s_corrected, 0.01, 1.5)

        except Exception:
            return None

    def _process_queue(self) -> None:
        """Process data queue in main thread."""
        try:
            for _ in range(50):  # Process up to 50 items per tick
                if self._data_queue.empty():
                    break

                data = self._data_queue.get_nowait()

                # Emit signal in main thread (Qt-safe)
                self.spectrum_ready.emit(data)

        except queue.Empty:
            pass
        except Exception:
            pass
