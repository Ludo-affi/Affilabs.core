from __future__ import annotations

"""Post-Calibration Dialog and Live View Transfer.

This module implements the post-calibration UI flow:
1. Show calibration results in dialog
2. Wait for user to click "Start" button
3. Transfer calibration to live acquisition system
4. Begin live SPR measurements

The transfer does NOT happen automatically - user must explicitly
click Start to begin live view.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from affilabs.utils.logger import logger


class PostCalibrationDialog(QDialog):
    """Dialog shown after calibration completes.

    Displays calibration results and waits for user to click Start
    before transferring to live view. User can also Cancel to abort.

    Signals:
        start_clicked: Emitted when user clicks Start button
        cancel_clicked: Emitted when user clicks Cancel button
    """

    start_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, calibration_result, parent=None) -> None:
        """Initialize post-calibration dialog.

        Args:
            calibration_result: LEDCalibrationResult object with calibration data
            parent: Parent widget

        """
        super().__init__(parent)

        self.calibration_result = calibration_result
        self.setup_ui()

    def setup_ui(self) -> None:
        """Setup the dialog UI."""
        self.setWindowTitle("Calibration Complete")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        # Main layout
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("[OK] Calibration Successful!")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Status message
        if self.calibration_result.success:
            status_text = "All channels calibrated successfully. Ready to start live measurements."
            status_color = "green"
        else:
            status_text = f"Calibration completed with errors on channels: {self.calibration_result.ch_error_list}"
            status_color = "orange"

        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"color: {status_color}; padding: 10px;")
        status_label.setWordWrap(True)
        status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_label)

        # Calibration summary group
        summary_group = QGroupBox("Calibration Summary")
        summary_layout = QGridLayout()

        row = 0

        # S-mode LED intensities
        summary_layout.addWidget(QLabel("S-Mode LED Intensities:"), row, 0)
        s_leds_text = ", ".join(
            [
                f"{ch.upper()}={val}"
                for ch, val in self.calibration_result.ref_intensity.items()
            ],
        )
        summary_layout.addWidget(QLabel(s_leds_text), row, 1)
        row += 1

        # P-mode LED intensities
        if self.calibration_result.p_mode_intensity:
            summary_layout.addWidget(QLabel("P-Mode LED Intensities:"), row, 0)
            p_leds_text = ", ".join(
                [
                    f"{ch.upper()}={val}"
                    for ch, val in self.calibration_result.p_mode_intensity.items()
                ],
            )
            summary_layout.addWidget(QLabel(p_leds_text), row, 1)
            row += 1

        # Integration time
        summary_layout.addWidget(QLabel("Integration Time:"), row, 0)
        summary_layout.addWidget(
            QLabel(f"{self.calibration_result.integration_time} ms"),
            row,
            1,
        )
        row += 1

        # Scans per channel
        summary_layout.addWidget(QLabel("Scans per Channel:"), row, 0)
        summary_layout.addWidget(QLabel(str(self.calibration_result.num_scans)), row, 1)
        row += 1

        # Calibration method
        summary_layout.addWidget(QLabel("Calibration Method:"), row, 0)
        method_text = (
            self.calibration_result.calibration_method
            if hasattr(self.calibration_result, "calibration_method")
            else "standard"
        )
        summary_layout.addWidget(QLabel(method_text.capitalize()), row, 1)
        row += 1

        # Timing synchronization (if available)
        if (
            hasattr(self.calibration_result, "timing_sync")
            and self.calibration_result.timing_sync
        ):
            timing = self.calibration_result.timing_sync

            summary_layout.addWidget(QLabel("Timing Synchronization:"), row, 0)

            # Format timing metrics with color coding based on status
            status = timing.get("status", "unknown")
            avg_cycle = timing.get("avg_cycle_ms", 0)
            jitter = timing.get("jitter_ms", 0)
            min_ms = timing.get("min_ms", 0)
            max_ms = timing.get("max_ms", 0)

            # Build timing text with metrics
            timing_text = f"{avg_cycle:.2f}ms avg, {jitter:.2f}ms jitter (min={min_ms:.2f}, max={max_ms:.2f})"

            # Create colored label based on status
            timing_label = QLabel(timing_text)
            if status == "pass":
                timing_label.setStyleSheet("color: green; font-weight: bold;")
            elif status == "warning":
                timing_label.setStyleSheet("color: orange; font-weight: bold;")
            elif status == "error":
                timing_label.setStyleSheet("color: red; font-weight: bold;")
            else:
                timing_label.setStyleSheet("color: gray;")

            summary_layout.addWidget(timing_label, row, 1)
            row += 1

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # Detailed log (scrollable)
        log_group = QGroupBox("Calibration Details")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)

        # Build detailed log text
        log_lines = []
        log_lines.append("=== Calibration Results ===\n")
        log_lines.append(
            f"Success: {'Yes' if self.calibration_result.success else 'No'}\n",
        )

        if self.calibration_result.ch_error_list:
            log_lines.append(
                f"Channels with Errors: {', '.join(self.calibration_result.ch_error_list)}\n",
            )

        if self.calibration_result.wave_data is not None:
            log_lines.append(
                f"\nWavelength Range: {len(self.calibration_result.wave_data)} pixels\n",
            )

        if self.calibration_result.dark_noise is not None:
            log_lines.append(
                f"Dark Noise Max: {max(self.calibration_result.dark_noise):.1f} counts\n",
            )

        if self.calibration_result.s_pol_ref:
            log_lines.append("\nS-Mode Reference Signals:\n")
            for ch, sig in self.calibration_result.s_pol_ref.items():
                log_lines.append(f"  Ch {ch.upper()}: max={max(sig):.0f} counts\n")

        if self.calibration_result.verification:
            log_lines.append("\n=== Quality Control ===\n")
            ver = self.calibration_result.verification
            if "fwhm" in ver:
                log_lines.append(f"FWHM: {ver['fwhm']:.1f} nm\n")
            if "snr" in ver:
                log_lines.append(f"SNR: {ver['snr']:.1f} dB\n")
            if "peak_position" in ver:
                log_lines.append(f"SPR Peak: {ver['peak_position']:.1f} nm\n")

        self.log_text.setPlainText("".join(log_lines))
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Instructions
        instructions = QLabel(
            "Click 'Start' to begin live measurements, or 'Cancel' to return to calibration menu.",
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            "padding: 10px; background-color: #f0f0f0; border-radius: 5px;",
        )
        layout.addWidget(instructions)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_button)

        self.start_button = QPushButton("Start")
        self.start_button.setMinimumWidth(100)
        self.start_button.setDefault(True)
        self.start_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #45a049; }",
        )
        self.start_button.clicked.connect(self._on_start)
        button_layout.addWidget(self.start_button)

        layout.addLayout(button_layout)

    def _on_start(self) -> None:
        """Handle Start button click."""
        logger.info("User clicked Start - transferring calibration to live view")
        self.start_clicked.emit()
        self.accept()

    def _on_cancel(self) -> None:
        """Handle Cancel button click."""
        logger.info("User clicked Cancel - returning to calibration menu")
        self.cancel_clicked.emit()
        self.reject()


def transfer_calibration_to_live_view(
    calibration_result,
    data_acquisition_manager,
    device_config,
) -> bool | None:
    """Transfer calibration results to live acquisition system.

    This function is called ONLY when user clicks the Start button
    in the post-calibration dialog. It does NOT happen automatically.

    Args:
        calibration_result: LEDCalibrationResult object
        data_acquisition_manager: DataAcquisitionManager instance
        device_config: DeviceConfiguration instance

    """
    logger.info("=" * 80)
    logger.info("🔄 TRANSFERRING CALIBRATION TO LIVE VIEW")
    logger.info("=" * 80)
    logger.info("User clicked Start button - beginning transfer...\n")

    try:
        # Save calibration to device config (full arrays)
        logger.info("Saving calibration to device_config.json...")
        save_calibration_to_device_config(
            calibration_result,
            device_config,
        )
        logger.info("[OK] Calibration saved to device config\n")

        # Transfer to data acquisition manager
        logger.info("Configuring live acquisition system...")

        # Set LED intensities
        data_acquisition_manager.set_led_intensities(
            s_mode=calibration_result.ref_intensity,
            p_mode=calibration_result.p_mode_intensity,
        )
        logger.info("[OK] LED intensities configured")
        logger.info(f"   S-mode: {calibration_result.ref_intensity}")
        logger.info(f"   P-mode: {calibration_result.p_mode_intensity}")

        # Set integration time and scans
        data_acquisition_manager.set_integration_time(
            calibration_result.integration_time,
        )
        data_acquisition_manager.set_num_scans(
            calibration_result.num_scans,
        )
        logger.info(f"[OK] Integration time: {calibration_result.integration_time}ms")
        logger.info(f"[OK] Scans per channel: {calibration_result.num_scans}")

        # Set reference signals and dark noise
        data_acquisition_manager.set_reference_signals(
            calibration_result.s_pol_ref,
        )
        data_acquisition_manager.set_dark_noise(
            calibration_result.dark_noise,
        )
        logger.info("[OK] Reference signals and dark noise configured")

        # Set wavelength data
        data_acquisition_manager.set_wavelength_data(
            calibration_result.wave_data,
        )
        logger.info(
            f"[OK] Wavelength data configured ({len(calibration_result.wave_data)} pixels)",
        )

        # If using alternative calibration (per-channel integration)
        if (
            hasattr(calibration_result, "per_channel_integration")
            and calibration_result.per_channel_integration
        ):
            logger.info("Using per-channel integration times (Global LED Mode)")
            data_acquisition_manager.set_per_channel_integration(
                calibration_result.per_channel_integration,
            )
            logger.info(
                f"[OK] Per-channel integration: {calibration_result.per_channel_integration}",
            )

        # Mark system as calibrated
        data_acquisition_manager.set_calibration_state(True)

        logger.info("\n" + "=" * 80)
        logger.info("[OK] TRANSFER COMPLETE - LIVE VIEW READY")
        logger.info("=" * 80)
        logger.info("System is now calibrated and ready for live measurements")
        logger.info("Starting live acquisition...")
        logger.info("=" * 80 + "\n")

        # Start live acquisition
        data_acquisition_manager.start_live_acquisition()

        return True

    except Exception as e:
        logger.exception(f"Failed to transfer calibration to live view: {e}")
        return False


def save_calibration_to_device_config(
    calibration_result,
    device_config,
) -> None:
    """Save calibration results to device_config.json with FULL arrays.

    This saves the complete calibration data, not just summary metrics.
    Includes full arrays for s_ref_signals, dark_noise, and wavelengths.

    Args:
        calibration_result: LEDCalibrationResult object
        device_config: DeviceConfiguration instance

    """
    logger.info("Saving calibration to device_config.json...")

    # Load existing calibration to check for fast-track counter
    existing_cal = device_config.load_led_calibration()
    is_fast_track = (
        hasattr(calibration_result, "fast_track_passed")
        and calibration_result.fast_track_passed
    )

    # Update fast-track counter
    if is_fast_track:
        # Increment counter for fast-track
        fast_track_count = existing_cal.get("fast_track_count", 0) + 1
        logger.info(f"[OK] Fast-track calibration #{fast_track_count}/5")
    else:
        # Reset counter for full calibration
        fast_track_count = 0
        logger.info("[OK] Full calibration - fast-track counter reset")

    # Build calibration data structure
    cal_data = {
        # LED intensities
        "s_mode_intensities": calibration_result.ref_intensity,
        "p_mode_intensities": calibration_result.p_mode_intensity,
        # Timing
        "integration_time_ms": calibration_result.integration_time,
        "num_scans": calibration_result.num_scans,
        # Calibration method
        "calibration_method": getattr(
            calibration_result,
            "calibration_method",
            "standard",
        ),
        # Fast-track tracking (Priority 1)
        "fast_track_count": fast_track_count,
        # Full arrays (not just metrics)
        "s_ref_signals": {
            ch: sig.tolist() for ch, sig in calibration_result.s_pol_ref.items()
        }
        if calibration_result.s_pol_ref
        else {},
        "p_ref_signals": {
            ch: sig.tolist() for ch, sig in calibration_result.p_pol_ref.items()
        }
        if hasattr(calibration_result, "p_pol_ref") and calibration_result.p_pol_ref
        else {},
        "dark_noise": calibration_result.dark_noise.tolist()
        if calibration_result.dark_noise is not None
        else [],
        "wavelengths": calibration_result.wave_data.tolist()
        if calibration_result.wave_data is not None
        else [],
        # Indices for ROI
        "wave_min_index": calibration_result.wave_min_index,
        "wave_max_index": calibration_result.wave_max_index,
        # QC metrics
        "s_ref_qc": calibration_result.s_ref_qc
        if hasattr(calibration_result, "s_ref_qc")
        else {},
        "verification": calibration_result.verification
        if hasattr(calibration_result, "verification")
        else {},
        # Metadata
        "success": calibration_result.success,
        "ch_error_list": calibration_result.ch_error_list,
        "calibration_date": None,  # Will be set by device_config.save_led_calibration()
    }

    # Add per-channel integration if using alternative method
    if (
        hasattr(calibration_result, "per_channel_integration")
        and calibration_result.per_channel_integration
    ):
        cal_data["per_channel_integration_times"] = (
            calibration_result.per_channel_integration
        )
        logger.info("Including per-channel integration times (Global LED Mode)")

    # Add per-channel dark noise if present
    if (
        hasattr(calibration_result, "per_channel_dark_noise")
        and calibration_result.per_channel_dark_noise
    ):
        cal_data["per_channel_dark_noise"] = {
            ch: dark.tolist()
            for ch, dark in calibration_result.per_channel_dark_noise.items()
        }
        logger.info("Including per-channel dark noise arrays")

    # Save to device config
    device_config.save_led_calibration(cal_data)

    # Log summary
    logger.info("[OK] Calibration saved with FULL arrays:")
    logger.info(
        f"   S-ref signals: {len(calibration_result.s_pol_ref)} channels × {len(calibration_result.wave_data)} pixels",
    )
    if hasattr(calibration_result, "p_pol_ref") and calibration_result.p_pol_ref:
        logger.info(
            f"   P-ref signals: {len(calibration_result.p_pol_ref)} channels × {len(calibration_result.wave_data)} pixels",
        )
    logger.info(f"   Dark noise: {len(calibration_result.dark_noise)} pixels")
    logger.info(f"   Wavelengths: {len(calibration_result.wave_data)} pixels")
    logger.info("   LED intensities: S-mode and P-mode")
    logger.info(f"   Integration: {calibration_result.integration_time}ms")
    logger.info(f"   Scans: {calibration_result.num_scans}")

    if cal_data.get("per_channel_integration_times"):
        logger.info(
            f"   Per-channel integration: {cal_data['per_channel_integration_times']}",
        )


def check_and_run_afterglow_calibration(
    device_config,
    usb,
    ctrl,
    calibration_result,
) -> bool | None:
    """Check if afterglow calibration exists, run if missing.

    This is called automatically after LED calibration completes.
    If afterglow calibration is missing from device config, it
    triggers automatic afterglow measurement.

    Args:
        device_config: DeviceConfiguration instance
        usb: Spectrometer instance
        ctrl: Controller instance
        calibration_result: LEDCalibrationResult with LED intensities

    Returns:
        bool: True if afterglow calibration exists or was completed

    """
    logger.info("\n" + "=" * 80)
    logger.info("Checking for afterglow calibration...")
    logger.info("=" * 80)

    try:
        # Check if afterglow calibration exists
        afterglow_data = device_config.load_afterglow_calibration()

        if afterglow_data and "channel_models" in afterglow_data:
            logger.info("[OK] Afterglow calibration found in device config")
            logger.info(
                f"   Calibrated channels: {list(afterglow_data['channel_models'].keys())}",
            )
            logger.info(
                f"   Calibration date: {afterglow_data.get('calibration_date', 'unknown')}",
            )
            logger.info("   No need to recalibrate\n")
            return True

        logger.warning("[WARN] Afterglow calibration NOT found in device config")
        logger.info("Running automatic afterglow calibration...")
        logger.info("This will take 5-10 minutes per channel\n")

        # Import afterglow calibration module
        from affilabs.utils.afterglow_calibration import run_afterglow_calibration

        # Run afterglow calibration using LED intensities from calibration
        afterglow_result = run_afterglow_calibration(
            usb,
            ctrl,
            led_intensities=calibration_result.s_mode_intensity,
            device_config=device_config,
            stop_flag=None,
            progress_callback=None,
        )

        if afterglow_result and afterglow_result.get("success"):
            logger.info("\n[OK] Automatic afterglow calibration complete")
            logger.info("   Results saved to device config")
            logger.info("=" * 80 + "\n")
            return True
        logger.error("\n[ERROR] Automatic afterglow calibration failed")
        logger.error("   System will operate without afterglow correction")
        logger.error("=" * 80 + "\n")
        return False

    except Exception as e:
        logger.exception(f"Failed to check/run afterglow calibration: {e}")
        logger.warning("System will operate without afterglow correction")
        return False
