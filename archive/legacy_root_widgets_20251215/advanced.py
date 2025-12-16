"""Advanced settings set during calibration."""

# Python version compatibility
try:
    from typing import Self  # Python 3.11+
except ImportError:
    from typing import Self  # Python < 3.11


from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QWidget

from ui.ui_p4spr_adv_settings import Ui_P4SPR_Advanced


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

    def load_calibration_params(self: Self, calibration_data) -> None:
        """Load parameters from calibration data into Advanced Settings.

        Args:
            calibration_data: CalibrationData object with integration_time, num_scans, LED intensities etc.

        """
        if not calibration_data:
            return

        try:
            # Load integration time from calibration
            integration_time = getattr(calibration_data, "integration_time", None)
            if integration_time:
                self.ui.intg_time.setText(str(int(integration_time)))

            # Load number of scans if available
            num_scans = getattr(calibration_data, "num_scans", None)
            if num_scans:
                self.ui.num_scans.setText(str(int(num_scans)))

            # Load LED intensities if available
            for led_name, attr_name in [
                ("led_int_a", "led_a_intensity"),
                ("led_int_b", "led_b_intensity"),
                ("led_int_c", "led_c_intensity"),
                ("led_int_d", "led_d_intensity"),
            ]:
                intensity = getattr(calibration_data, attr_name, None)
                if intensity is not None:
                    self.ui.__getattribute__(led_name).setText(str(intensity))

        except Exception as e:
            print(
                f"Warning: Could not load calibration params into Advanced Settings: {e}",
            )

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
        settings_dict = {
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
        }

        # Save integration time override to settings module for live acquisition
        try:
            import settings

            intg_time_str = self.ui.intg_time.text()
            if intg_time_str and intg_time_str.strip():
                settings.DETECTOR_ON_TIME_MS = int(intg_time_str)
                print(
                    f"Advanced Settings: Integration time override set to {settings.DETECTOR_ON_TIME_MS}ms",
                )
        except Exception as e:
            print(f"Warning: Could not save integration time to settings: {e}")

        # Emit signal for backward compatibility
        self.new_parameter_sig.emit(settings_dict)
