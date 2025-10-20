"""Advanced settings set during calibration."""

from typing import Self

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QWidget

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

    def __init__(self: Self, parent: QWidget | None = None) -> None:
        """Create the advance settings widget."""
        super().__init__(parent)
        self.ui = Ui_P4SPR_Advanced()
        self.ui.setupUi(self)
        self.ui.set_btn.clicked.connect(self.update_settings)
        self.setWindowFlag(Qt.WindowType.Tool)

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
