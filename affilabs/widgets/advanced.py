from __future__ import annotations

"""Advanced settings set during calibration."""

from typing import Self

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QWidget, QPushButton, QLabel, QCheckBox, QGroupBox, QVBoxLayout

from ui.ui_p4spr_adv_settings import Ui_P4SPR_Advanced


class P4SPRAdvMenu(QDialog):
    """Advanced settings widget for the P4SPR.

    These settings are set automatically during calibration.
    """

    new_parameter_sig = Signal(dict)
    get_parameter_sig = Signal()
    measure_afterglow_sig = Signal()
    quality_monitoring_toggled = Signal(bool)

    def __init__(self: Self, parent: QWidget | None = None) -> None:
        """Create the advance settings widget."""
        super().__init__(parent)
        self.ui = Ui_P4SPR_Advanced()
        self.ui.setupUi(self)
        self.ui.set_btn.clicked.connect(self.update_settings)
        self.setWindowFlag(Qt.WindowType.Tool)

        # Add session quality monitoring UI section
        self._setup_quality_monitoring_ui()

        # Hidden OEM/factory feature: optical calibration (LED afterglow characterization)
        # NOT exposed to end-users - this is factory/service terminology
        self.measure_afterglow_btn = QPushButton("Run Optical Calibration…", self)
        self.measure_afterglow_btn.setToolTip(
            "[OEM/Factory Only] Characterize optical system response across integration times.\n"
            "This measures LED phosphor decay characteristics for correction algorithms."
        )
        # Add next to Update Settings button at the bottom
        try:
            self.ui.horizontalLayout.addWidget(self.measure_afterglow_btn)
        except Exception:
            # Fallback: place in dialog if layout not exposed
            self.measure_afterglow_btn.setParent(self)
        self.measure_afterglow_btn.clicked.connect(self._emit_measure_afterglow)
        # Hidden by default; shown only when enabled by host app
        self.measure_afterglow_btn.setVisible(False)

        # Small status line for LED/post delays and afterglow file
        self.delay_status = QLabel(self)
        self.delay_status.setObjectName("delay_status")
        try:
            # Insert just above the bottom button frame
            idx = self.ui.verticalLayout.indexOf(self.ui.frame)
            self.ui.verticalLayout.insertWidget(max(0, idx), self.delay_status)
        except Exception:
            self.ui.verticalLayout.addWidget(self.delay_status)
        self.set_delay_status(led_delay_s=None, post_delay_s=None, dyn_led=False, dyn_post=False, cal_path=None)
        # Hide delay status by default (shown only in DEV mode)
        self.delay_status.setVisible(False)

    def enable_afterglow_button(self: Self, visible: bool) -> None:
        """Show or hide the optical calibration button (OEM/factory feature only).

        Note: Despite method name 'afterglow', the button text is 'Optical Calibration'
        to use customer-facing terminology instead of internal technical terms.
        """
        self.measure_afterglow_btn.setVisible(bool(visible))

    def enable_delay_status(self: Self, visible: bool) -> None:
        """Show or hide the delay status label."""
        self.delay_status.setVisible(bool(visible))

    def _setup_quality_monitoring_ui(self: Self) -> None:
        """Add session quality monitoring controls to advanced settings."""
        try:
            # Create quality monitoring group box
            self.quality_group = QGroupBox("Session Quality Monitoring (FWHM-based QC)", self)
            quality_layout = QVBoxLayout()

            # Add checkbox for enable/disable
            self.quality_monitoring_checkbox = QCheckBox("Enable session-based FWHM quality tracking", self)
            self.quality_monitoring_checkbox.setToolTip(
                "Track Full Width at Half Maximum (FWHM) of SPR peaks during recording.\n"
                "Provides real-time quality assessment with RGB LED feedback:\n"
                "  • Green: Excellent (FWHM < 30nm)\n"
                "  • Yellow: Good (FWHM 30-60nm)\n"
                "  • Red: Poor (FWHM ≥ 60nm)\n\n"
                "Only tracks peaks within 580-630nm wavelength range.\n"
                "Generates end-of-session QC report with historical comparison."
            )
            self.quality_monitoring_checkbox.stateChanged.connect(self._on_quality_monitoring_changed)
            quality_layout.addWidget(self.quality_monitoring_checkbox)

            # Add info label
            info_label = QLabel(
                "<small>Thresholds: <b>&lt;30nm</b> excellent, <b>30-60nm</b> good, <b>≥60nm</b> poor<br/>"
                "Valid range: 580-630nm wavelength</small>",
                self
            )
            info_label.setWordWrap(True)
            quality_layout.addWidget(info_label)

            self.quality_group.setLayout(quality_layout)

            # Insert above the bottom button frame
            idx = self.ui.verticalLayout.indexOf(self.ui.frame)
            self.ui.verticalLayout.insertWidget(max(0, idx), self.quality_group)

        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Could not add quality monitoring UI: {e}")

    def _on_quality_monitoring_changed(self: Self, state: int) -> None:
        """Handle quality monitoring checkbox state change."""
        enabled = (state == Qt.CheckState.Checked.value)
        self.quality_monitoring_toggled.emit(enabled)

    def set_quality_monitoring_state(self: Self, enabled: bool) -> None:
        """Set the quality monitoring checkbox state without emitting signal."""
        try:
            self.quality_monitoring_checkbox.blockSignals(True)
            self.quality_monitoring_checkbox.setChecked(enabled)
            self.quality_monitoring_checkbox.blockSignals(False)
        except Exception:
            pass

    def _emit_measure_afterglow(self: Self) -> None:
        # Give immediate local feedback in the dialog
        try:
            if hasattr(self, "delay_status"):
                self.delay_status.setText("Starting afterglow calibration…")
        except Exception:
            pass
        self.measure_afterglow_sig.emit()

    def set_delay_status(
        self: Self,
        *,
        led_delay_s: float | None,
        post_delay_s: float | None,
        dyn_led: bool,
        dyn_post: bool,
        cal_path: str | None,
    ) -> None:
        """Update the small status line to reflect current delays and calibration file.

        If values are None, show defaults as unknown.
        """
        try:
            pre_ms = f"{led_delay_s*1000:.1f} ms" if isinstance(led_delay_s, (int, float)) else "—"
            post_ms = f"{post_delay_s*1000:.1f} ms" if isinstance(post_delay_s, (int, float)) else "—"
            dyn_txt = f"pre {'On' if dyn_led else 'Off'}, post {'On' if dyn_post else 'Off'}"
            cal_txt = cal_path if cal_path else "None"
            # Shorten very long paths by showing basename when possible
            try:
                import os
                if cal_path:
                    cal_txt = os.path.basename(cal_path)
            except Exception:
                pass
            self.delay_status.setText(f"Pre: {pre_ms}  •  Post: {post_ms}  •  Dynamic: {dyn_txt}  •  Cal: {cal_txt}")
            self.delay_status.setToolTip(cal_path or "No calibration file configured")
        except Exception:
            # Fallback minimal text
            self.delay_status.setText("Pre/Post delay status unavailable")

    def set_status_text(self: Self, text: str) -> None:
        """Directly set the status line text.

        Used for transient messages like start/progress/completion updates.
        """
        try:
            self.delay_status.setText(str(text))
        except Exception:
            pass

    def refresh_values(self: Self) -> None:
        """Refresh value.

        Not sure what this does.
        """
        self.get_parameter_sig.emit()

    def display_settings(self: Self, settings: dict[str, object]) -> None:
        """Display the given settings in the widget."""
        for setting in [
            "led_del",
            "ht_req",
            "sens_interval",
            "intg_time",
            "num_scans",
            "led_int_a",
            "led_int_b",
            "led_int_c",
            "led_int_d",
            "s_pos",
            "p_pos",
            "pump_1_correction",
            "pump_2_correction",
        ]:
            self.ui.__getattribute__(setting).setText(str(settings[setting]))

    def update_settings(self: Self) -> None:
        """Update settings with current widget entries."""
        self.new_parameter_sig.emit(
            {
                "led_del": self.ui.led_del.text(),
                "ht_req": self.ui.ht_req.text(),
                "sens_interval": self.ui.sens_interval.text(),
                "intg_time": self.ui.intg_time.text(),
                "num_scans": self.ui.num_scans.text(),
                "led_int_a": self.ui.led_int_a.text(),
                "led_int_b": self.ui.led_int_b.text(),
                "led_int_c": self.ui.led_int_c.text(),
                "led_int_d": self.ui.led_int_d.text(),
                "s_pos": self.ui.s_pos.text(),
                "p_pos": self.ui.p_pos.text(),
                "pump_1_correction": self.ui.pump_1_correction.text(),
                "pump_2_correction": self.ui.pump_2_correction.text(),
            },
        )
