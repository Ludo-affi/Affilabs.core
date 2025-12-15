"""Diagnostics Dialog module extracted from LL_UI_v1_0.py for modularity."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from affilabs.ui_styles import (
    Colors,
    Dimensions,
    Fonts,
    group_box_style,
    label_style,
    primary_button_style,
    scrollbar_style,
    text_edit_log_style,
    title_style,
)


class DiagnosticsDialog(QDialog):
    """Diagnostics Dialog showing all QC details and calibration data.

    Only visible in DEV/support mode.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Diagnostics")
        self.setModal(True)
        self.setMinimumSize(800, 700)
        self.setStyleSheet("QDialog { background: white; }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        title = QLabel("🔧 System Diagnostics & Quality Control")
        title.setStyleSheet(title_style(20) + "margin-bottom: 8px;")
        main_layout.addWidget(title)

        subtitle = QLabel("Developer / Support Mode")
        subtitle.setStyleSheet(label_style(12, color=Colors.WARNING, weight=600))
        main_layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.frameShape().NoFrame)
        scroll.setStyleSheet(scrollbar_style())

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)

        cal_group = self._create_group(
            "📊 Calibration Data",
            [
                ("Integration Time:", "integration_time_diag"),
                ("Number of Scans:", "num_scans_diag"),
                ("LED Intensity A:", "led_a_diag"),
                ("LED Intensity B:", "led_b_diag"),
                ("LED Intensity C:", "led_c_diag"),
                ("LED Intensity D:", "led_d_diag"),
                ("S-mode Position:", "s_pos_diag"),
                ("P-mode Position:", "p_pos_diag"),
                ("Calibration Date:", "cal_date_diag"),
            ],
        )
        scroll_layout.addWidget(cal_group)

        sref_group = self._create_group(
            "📈 S-ref Signal Quality",
            [
                ("Channel A Signal:", "sref_a_diag"),
                ("Channel B Signal:", "sref_b_diag"),
                ("Channel C Signal:", "sref_c_diag"),
                ("Channel D Signal:", "sref_d_diag"),
                ("Target Counts:", "sref_target_diag"),
                ("Detector Max:", "detector_max_diag"),
                ("A QC Status:", "sref_a_qc_diag"),
                ("B QC Status:", "sref_b_qc_diag"),
                ("C QC Status:", "sref_c_qc_diag"),
                ("D QC Status:", "sref_d_qc_diag"),
            ],
        )
        scroll_layout.addWidget(sref_group)

        fwhm_group = self._create_group(
            "📐 Peak Quality Metrics (FWHM)",
            [
                ("Channel A FWHM:", "fwhm_a_diag"),
                ("Channel B FWHM:", "fwhm_b_diag"),
                ("Channel C FWHM:", "fwhm_c_diag"),
                ("Channel D FWHM:", "fwhm_d_diag"),
                ("FWHM Thresholds:", "fwhm_thresholds_diag"),
                ("Session Avg FWHM:", "fwhm_session_avg_diag"),
                ("Quality Monitoring:", "quality_monitoring_status_diag"),
            ],
        )
        scroll_layout.addWidget(fwhm_group)

        detector_group = self._create_group(
            "🔬 Detector Specifications",
            [
                ("Detector Type:", "detector_type_diag"),
                ("Detector Serial:", "detector_serial_diag"),
                ("Num Pixels:", "num_pixels_diag"),
                ("Wavelength Range:", "wavelength_range_diag"),
                ("Max Counts:", "max_counts_diag"),
                ("Target Counts (75%):", "target_counts_diag"),
            ],
        )
        scroll_layout.addWidget(detector_group)

        status_group = self._create_group(
            "⚙ System Status",
            [
                ("Calibrated:", "calibrated_status_diag"),
                ("Live Data Enabled:", "live_data_status_diag"),
                ("Current Pipeline:", "pipeline_diag"),
                ("Afterglow Model:", "afterglow_model_diag"),
                ("PRE LED Delay:", "pre_led_delay_diag"),
                ("POST LED Delay:", "post_led_delay_diag"),
            ],
        )
        scroll_layout.addWidget(status_group)

        log_group = QGroupBox("📝 Recent Debug Log")
        log_group.setStyleSheet(group_box_style())
        log_layout = QVBoxLayout()

        self.diag_log_output = QTextEdit()
        self.diag_log_output.setReadOnly(True)
        self.diag_log_output.setStyleSheet(text_edit_log_style())
        self.diag_log_output.setMinimumHeight(200)
        self.diag_log_output.setPlainText(
            "Log output will appear here when available...",
        )
        log_layout.addWidget(self.diag_log_output)
        log_group.setLayout(log_layout)
        scroll_layout.addWidget(log_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.setStyleSheet(primary_button_style(Dimensions.BUTTON_HEIGHT_SM))
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _create_group(self, title, fields):
        group = QGroupBox(title)
        group.setStyleSheet(group_box_style())
        layout = QGridLayout()
        layout.setSpacing(12)
        layout.setColumnStretch(1, 1)
        for row, (label_text, attr_name) in enumerate(fields):
            label = QLabel(label_text)
            label.setStyleSheet(
                label_style(12, color=Colors.SECONDARY_TEXT, weight=500),
            )
            value = QLabel("N/A")
            value.setStyleSheet(
                label_style(
                    12,
                    color=Colors.PRIMARY_TEXT,
                    weight=400,
                    font_family=Fonts.MONOSPACE,
                ),
            )
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            setattr(self, attr_name, value)
            layout.addWidget(
                label,
                row,
                0,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            )
            layout.addWidget(value, row, 1)
        group.setLayout(layout)
        return group

    def load_diagnostics_data(self, main_window):
        if not main_window or not hasattr(main_window, "app"):
            return
        app = main_window.app
        if hasattr(app, "data_mgr") and app.data_mgr:
            self.integration_time_diag.setText(
                f"{app.data_mgr.integration_time:.2f} ms",
            )
            self.num_scans_diag.setText(str(app.data_mgr.num_scans))
            if (
                hasattr(app.data_mgr, "leds_calibrated")
                and app.data_mgr.leds_calibrated
            ):
                leds = app.data_mgr.leds_calibrated
                self.led_a_diag.setText(f"{leds.get('a', 'N/A')}/255")
                self.led_b_diag.setText(f"{leds.get('b', 'N/A')}/255")
                self.led_c_diag.setText(f"{leds.get('c', 'N/A')}/255")
                self.led_d_diag.setText(f"{leds.get('d', 'N/A')}/255")
            if (
                hasattr(app.data_mgr, "calibration_data")
                and app.data_mgr.calibration_data
                and app.data_mgr.calibration_data.s_pol_ref
            ):
                import numpy as np

                for ch in ["a", "b", "c", "d"]:
                    if ch in app.data_mgr.calibration_data.s_pol_ref:
                        sig = app.data_mgr.calibration_data.s_pol_ref[ch]
                        max_val = np.max(sig) if len(sig) > 0 else 0
                        getattr(self, f"sref_{ch}_diag").setText(
                            f"{max_val:.0f} counts",
                        )
        if hasattr(app, "hardware_mgr") and app.hardware_mgr:
            if hasattr(app.hardware_mgr, "usb") and app.hardware_mgr.usb:
                usb = app.hardware_mgr.usb
                if hasattr(usb, "serial_number") and usb.serial_number:
                    self.detector_serial_diag.setText(usb.serial_number)
                if hasattr(usb, "max_counts"):
                    self.detector_max_diag.setText(f"{usb.max_counts} counts")
                    self.max_counts_diag.setText(f"{usb.max_counts}")
                    self.sref_target_diag.setText(
                        f"{int(usb.max_counts * 0.75)} counts (75%)",
                    )
                if hasattr(usb, "target_counts"):
                    self.target_counts_diag.setText(f"{usb.target_counts}")
                if hasattr(usb, "num_pixels"):
                    self.num_pixels_diag.setText(f"{usb.num_pixels}")
                if hasattr(usb, "wavelengths") and usb.wavelengths is not None:
                    wl = usb.wavelengths
                    self.wavelength_range_diag.setText(f"{wl[0]:.1f} - {wl[-1]:.1f} nm")
            if hasattr(app.hardware_mgr, "ctrl") and app.hardware_mgr.ctrl:
                self.detector_type_diag.setText("USB4000/Flame-T (Ocean Optics)")
        self.calibrated_status_diag.setText(
            "✓ Yes" if getattr(app, "calibrated", False) else "✗ No",
        )
        self.live_data_status_diag.setText(
            "✓ Enabled"
            if getattr(main_window, "live_data_enabled", False)
            else "✗ Disabled",
        )
        if hasattr(app, "quality_monitor"):
            qm = app.quality_monitor
            if hasattr(qm, "FWHM_EXCELLENT") and hasattr(qm, "FWHM_GOOD"):
                self.fwhm_thresholds_diag.setText(
                    f"Excellent: <{qm.FWHM_EXCELLENT}nm, Good: <{qm.FWHM_GOOD}nm, Poor: ≥{qm.FWHM_GOOD}nm",
                )
        if hasattr(app.data_mgr, "pipeline"):
            pipeline = app.data_mgr.pipeline
            if hasattr(pipeline, "name"):
                self.pipeline_diag.setText(pipeline.name)
            elif hasattr(pipeline, "description"):
                self.pipeline_diag.setText(pipeline.description)
        try:
            from affilabs.utils.logger import logger

            if hasattr(logger, "handlers") and len(logger.handlers) > 0:
                import logging

                for handler in logger.handlers:
                    if isinstance(handler, logging.FileHandler):
                        log_file = handler.baseFilename
                        try:
                            with open(log_file) as f:
                                lines = f.readlines()
                                last_lines = "".join(lines[-100:])
                                self.diag_log_output.setPlainText(last_lines)
                        except Exception as e:
                            self.diag_log_output.setPlainText(
                                f"Could not read log file: {e}",
                            )
                        break
        except Exception as e:
            self.diag_log_output.setPlainText(f"Log output unavailable: {e}")
