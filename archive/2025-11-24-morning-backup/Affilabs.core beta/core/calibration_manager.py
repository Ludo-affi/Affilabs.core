"""Simplified Calibration Manager - Direct path from UI to backend.

This replaces the fragmented calibration system with a single, clean interface.
"""

import threading

from PySide6.QtCore import QObject, Signal

from utils.logger import logger


class CalibrationManager(QObject):
    """Manages LED calibration with direct backend access.

    Signals:
        calibration_started: Emitted when calibration begins
        calibration_progress: Emitted with (message: str, percent: int)
        calibration_complete: Emitted with calibration data dict
        calibration_failed: Emitted with error message string
    """

    calibration_started = Signal()
    calibration_progress = Signal(str, int)  # (message, percent)
    calibration_complete = Signal(dict)
    calibration_failed = Signal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._thread = None
        self._running = False

    def start_calibration(self):
        """Start calibration in background thread."""
        if self._running:
            logger.warning("Calibration already in progress")
            return False

        logger.info("🎬 Starting LED calibration...")
        self._running = True
        self.calibration_started.emit()

        # Run in background thread
        self._thread = threading.Thread(
            target=self._run_calibration,
            daemon=True,
            name="CalibrationManager",
        )
        self._thread.start()
        return True

    def _run_calibration(self):
        """Main calibration routine (runs in background thread)."""
        try:
            print("=" * 70)
            print("CALIBRATION MANAGER: _run_calibration() STARTED")
            print("=" * 70)

            # Get hardware directly
            self.calibration_progress.emit("Initializing...", 5)

            hardware_mgr = self.app.hardware_mgr
            ctrl = hardware_mgr.ctrl
            usb = hardware_mgr.usb

            print("Hardware check:")
            print(f"  ctrl = {ctrl}")
            print(f"  usb = {usb}")
            logger.info("🔍 Hardware check:")
            logger.info(
                f"   ctrl = {ctrl} (type: {type(ctrl).__name__ if ctrl else 'None'})",
            )
            logger.info(
                f"   usb = {usb} (type: {type(usb).__name__ if usb else 'None'})",
            )

            if not ctrl:
                raise RuntimeError(
                    "Controller not connected. Please connect the P4SPR controller.",
                )

            if not usb:
                raise RuntimeError(
                    "Spectrometer not connected. Please connect the USB4000.",
                )

            # Test controller communication
            try:
                print("Testing controller...")
                print(f"  Controller type: {type(ctrl).__name__}")
                print(
                    f"  Controller methods: {[m for m in dir(ctrl) if not m.startswith('_')][:10]}",
                )

                logger.info("Testing controller communication...")

                # Try turning off channels
                result = ctrl.turn_off_channels()
                print(f"  turn_off_channels() returned: {result}")

                # Try turning on LED A
                print("  Testing LED A activation...")
                result = ctrl.turn_on_channel("a")
                print(f"  turn_on_channel('a') returned: {result}")

                import time

                time.sleep(0.5)

                # Try setting intensity
                print("  Testing LED A intensity...")
                result = ctrl.set_intensity("a", 200)
                print(f"  set_intensity('a', 200) returned: {result}")

                time.sleep(0.5)

                # Turn off
                ctrl.turn_off_channels()

                print("✅ Controller OK")
                logger.info("✅ Controller responding to commands")
            except Exception as e:
                print(f"❌ Controller test failed: {e}")
                logger.error(f"❌ Controller test failed: {e}")
                import traceback

                traceback.print_exc()
                raise RuntimeError(f"Controller communication error: {e}")

            print("✅ Hardware ready")
            logger.info("✅ Hardware ready - proceeding with calibration")

            # Load configuration
            self.calibration_progress.emit("Loading configuration...", 10)
            from settings import INTEGRATION_STEP, MAX_WAVELENGTH, MIN_WAVELENGTH
            from utils.device_configuration import DeviceConfiguration

            device_serial = getattr(usb, "serial_number", None)
            device_config = DeviceConfiguration(device_serial=device_serial)

            # Step 3: Read wavelength data
            self.calibration_progress.emit("Reading wavelength data...", 15)
            wave_data = usb.read_wavelength()
            wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
            wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)

            # Step 4: Load afterglow correction if available
            afterglow_correction = None
            try:
                from afterglow_correction import AfterglowCorrection

                from utils.device_integration import get_device_optical_calibration_path

                optical_cal_path = get_device_optical_calibration_path()
                if optical_cal_path and optical_cal_path.exists():
                    afterglow_correction = AfterglowCorrection(optical_cal_path)
                    logger.info(
                        f"✅ Loaded afterglow correction: {optical_cal_path.name}",
                    )
            except Exception as e:
                logger.debug(f"Afterglow correction not available: {e}")

            # Step 5: Run calibration (this is the working backend code)
            logger.info("🚀 Starting LED calibration backend...")
            from utils.led_calibration import perform_full_led_calibration

            def progress_update(msg):
                """Map backend messages to progress percentages."""
                if "integration" in msg.lower():
                    self.calibration_progress.emit(msg, 25)
                elif "calibrating led a" in msg.lower():
                    self.calibration_progress.emit(msg, 35)
                elif "calibrating led b" in msg.lower():
                    self.calibration_progress.emit(msg, 45)
                elif "calibrating led c" in msg.lower():
                    self.calibration_progress.emit(msg, 55)
                elif "calibrating led d" in msg.lower():
                    self.calibration_progress.emit(msg, 65)
                elif "dark noise" in msg.lower():
                    self.calibration_progress.emit(msg, 70)
                elif "reference signal" in msg.lower():
                    self.calibration_progress.emit(msg, 75)
                elif "p-mode" in msg.lower():
                    self.calibration_progress.emit(msg, 85)
                else:
                    logger.info(f"Progress: {msg}")

            cal_result = perform_full_led_calibration(
                usb=usb,
                ctrl=ctrl,
                device_type="P4SPR",
                single_mode=False,
                single_ch="a",
                integration_step=INTEGRATION_STEP,
                stop_flag=None,
                progress_callback=progress_update,
                wave_data=wave_data,
                wave_min_index=wave_min_index,
                wave_max_index=wave_max_index,
                device_config=device_config,
                afterglow_correction=afterglow_correction,
            )

            # Step 6: Validate results
            self.calibration_progress.emit("Validating results...", 90)

            logger.info("🔍 Calibration result validation:")
            logger.info(f"   success: {cal_result.success}")
            logger.info(f"   integration_time: {cal_result.integration_time}")
            logger.info(
                f"   ref_sig channels: {list(cal_result.ref_sig.keys()) if cal_result.ref_sig else 'None'}",
            )
            logger.info(f"   ch_error_list: {cal_result.ch_error_list}")

            if not cal_result.success:
                error_msg = getattr(cal_result, "error_message", None) or getattr(
                    cal_result,
                    "error",
                    None,
                )
                if not error_msg:
                    # Check for channel errors
                    if cal_result.ch_error_list:
                        error_msg = f"Calibration failed for channels: {', '.join(cal_result.ch_error_list)}"
                    else:
                        error_msg = "Calibration completed but marked as unsuccessful"
                logger.error(f"❌ Calibration validation failed: {error_msg}")
                raise RuntimeError(f"Calibration failed: {error_msg}")

            if not cal_result.ref_sig or len(cal_result.ref_sig) == 0:
                raise RuntimeError("No reference spectra acquired")

            logger.info("✅ Calibration backend completed successfully")

            # Step 7: Store results in data_mgr
            self.calibration_progress.emit("Storing results...", 95)

            data_mgr = self.app.data_mgr
            data_mgr.integration_time = cal_result.integration_time
            data_mgr.num_scans = cal_result.num_scans
            data_mgr.ref_intensity = cal_result.ref_intensity
            data_mgr.leds_calibrated = cal_result.leds_calibrated
            data_mgr.dark_noise = cal_result.dark_noise
            data_mgr.wave_data = cal_result.wave_data
            data_mgr.ref_sig = cal_result.ref_sig
            data_mgr.ch_error_list = cal_result.ch_error_list.copy()
            data_mgr.s_ref_qc_results = getattr(cal_result, "s_ref_qc_results", {})
            data_mgr.channel_performance = getattr(
                cal_result,
                "channel_performance",
                {},
            )

            # Store wavelength indices
            data_mgr.wave_min_index = wave_min_index
            data_mgr.wave_max_index = wave_max_index

            # Calculate Fourier weights
            data_mgr._calculate_snr_aware_fourier_weights()

            # Mark as calibrated
            data_mgr.calibrated = True

            # Load afterglow correction for live acquisition (if method exists)
            afterglow_available = False
            try:
                if hasattr(data_mgr, "_load_afterglow_correction"):
                    data_mgr._load_afterglow_correction()
                    afterglow_available = (
                        getattr(data_mgr, "_afterglow_correction", None) is not None
                    )
            except Exception as e:
                logger.debug(f"Afterglow loading skipped: {e}")

            logger.info("✅ Calibration data stored in data_mgr")

            # Step 8: Prepare calibration data for UI
            calibration_data = {
                "integration_time": cal_result.integration_time,
                "num_scans": cal_result.num_scans,
                "ref_intensity": cal_result.ref_intensity,
                "leds_calibrated": cal_result.leds_calibrated.copy(),
                "ch_error_list": cal_result.ch_error_list.copy(),
                "s_ref_qc_results": data_mgr.s_ref_qc_results,
                "channel_performance": data_mgr.channel_performance,
                "calibration_type": "full",
                "afterglow_available": afterglow_available,
            }

            # Complete
            self.calibration_progress.emit("Complete!", 100)
            self.calibration_complete.emit(calibration_data)

            logger.info("✅ Calibration complete - all channels calibrated")

        except Exception as e:
            logger.error(f"❌ Calibration failed: {e}", exc_info=True)
            self.calibration_failed.emit(str(e))
        finally:
            self._running = False

    def is_running(self):
        """Check if calibration is currently running."""
        return self._running
