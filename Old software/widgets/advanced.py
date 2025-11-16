"""Advanced settings set during calibration."""

from typing import Self

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QWidget, QPushButton, QLabel

from ui.ui_p4spr_adv_settings import Ui_P4SPR_Advanced
from ui.ui_qspr_adv_settings import Ui_QSPR_Advanced


class QSPRAdvMenu(QDialog):
    """QSPR advanced settings. QSPR is obsolete, so not documenting much."""

    new_parameter_sig = Signal(dict)
    get_parameter_sig = Signal()

    def __init__(self: Self, parent: QWidget | None = None) -> None:
        """Make it."""
        super().__init__(parent)

        self.ui = Ui_QSPR_Advanced()
        self.ui.setupUi(self)
        self.ui.set_btn.clicked.connect(self.update_settings)
        self.setWindowFlag(Qt.WindowType.Tool)

    def refresh_values(self: Self) -> None:
        """Refresh values."""
        self.get_parameter_sig.emit()

    def display_settings(self: Self, settings: dict[str, object]) -> None:
        """Display settings."""
        for setting in [
            "s_pos",
            "p_pos",
            "up_time",
            "down_time",
            "adj_time",
            "debounce",
            "start_interval",
        ]:
            self.ui.__getattribute__(setting).setText(str(settings[setting]))

    def update_settings(self: Self) -> None:
        """Update settings."""
        self.new_parameter_sig.emit(
            {
                "s_pos": self.ui.s_pos.text(),
                "p_pos": self.ui.p_pos.text(),
                "up_time": self.ui.up_time.text(),
                "down_time": self.ui.down_time.text(),
                "adj_time": self.ui.adj_time.text(),
                "debounce": self.ui.debounce.text(),
                "start_interval": self.ui.start_interval.text(),
            },
        )


class P4SPRAdvMenu(QDialog):
    """Advanced settings widget for the P4SPR.

    These settings are set automatically during calibration.
    """

    new_parameter_sig = Signal(dict)
    get_parameter_sig = Signal()
    measure_afterglow_sig = Signal()

    def __init__(self: Self, parent: QWidget | None = None) -> None:
        """Create the advance settings widget."""
        super().__init__(parent)
        self.ui = Ui_P4SPR_Advanced()
        self.ui.setupUi(self)
        self.ui.set_btn.clicked.connect(self.update_settings)
        self.setWindowFlag(Qt.WindowType.Tool)

        # Hidden advanced action: measure LED afterglow calibration
        self.measure_afterglow_btn = QPushButton("Measure Afterglow…", self)
        self.measure_afterglow_btn.setToolTip("Run optical afterglow calibration to model LED decay")
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

    def enable_afterglow_button(self: Self, visible: bool) -> None:
        """Show or hide the afterglow measurement button."""
        self.measure_afterglow_btn.setVisible(bool(visible))

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
