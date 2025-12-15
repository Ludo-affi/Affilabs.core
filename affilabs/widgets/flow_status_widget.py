"""Flow Status Widget - Displays device status warnings in the Flow tab."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class FlowStatusWidget(QWidget):
    """Widget displaying device status warnings at the top of the Flow tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._status_data = {
            "sensor": "Unknown",
            "optics": "Unknown",
            "fluidics": "Unknown",
            "spr_connected": False,
            "knx_connected": False,
            "pump_connected": False,
        }
        # Initialize with default message
        self.update_status()

    def _setup_ui(self):
        """Set up the status message UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        # Status message container
        self.status_container = QFrame(self)
        self.status_container.setObjectName("status_container")
        self.status_container.setStyleSheet(
            "QFrame#status_container {"
            "    background-color: rgb(255, 243, 205);"
            "    border: 1px solid rgb(255, 193, 7);"
            "    border-radius: 8px;"
            "    padding: 12px;"
            "}",
        )

        container_layout = QVBoxLayout(self.status_container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(4)

        # Title
        self.title_label = QLabel("System Status", self.status_container)
        title_font = QFont()
        title_font.setPointSize(9)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(
            "color: rgb(102, 77, 3); background: transparent; border: none;",
        )
        container_layout.addWidget(self.title_label)

        # Status message
        self.message_label = QLabel(
            "Waiting for device status...",
            self.status_container,
        )
        self.message_label.setWordWrap(True)
        message_font = QFont()
        message_font.setPointSize(9)
        self.message_label.setFont(message_font)
        self.message_label.setStyleSheet(
            "color: rgb(102, 77, 3); background: transparent; border: none;",
        )
        container_layout.addWidget(self.message_label)

        layout.addWidget(self.status_container)

    def update_device_status(
        self,
        spr_connected=None,
        knx_connected=None,
        pump_connected=None,
    ):
        """Update device connection status.

        Args:
            spr_connected: Whether SPR device is connected
            knx_connected: Whether KNX system is connected
            pump_connected: Whether pump is connected

        """
        if spr_connected is not None:
            self._status_data["spr_connected"] = spr_connected
        if knx_connected is not None:
            self._status_data["knx_connected"] = knx_connected
        if pump_connected is not None:
            self._status_data["pump_connected"] = pump_connected

        self.update_status()

    def update_system_status(
        self,
        sensor_status=None,
        optics_status=None,
        fluidics_status=None,
    ):
        """Update system component status.

        Args:
            sensor_status: Status for Sensor ("Good", "Caution", "Poor", "Unknown")
            optics_status: Status for Optics ("Good", "Caution", "Poor", "Unknown")
            fluidics_status: Status for Fluidics ("Good", "Caution", "Poor", "Unknown")

        """
        if sensor_status is not None:
            self._status_data["sensor"] = sensor_status
        if optics_status is not None:
            self._status_data["optics"] = optics_status
        if fluidics_status is not None:
            self._status_data["fluidics"] = fluidics_status

        self.update_status()

    def update_status(self):
        """Update the status message based on current device and system status."""
        warnings = []

        # Check device connections
        if not self._status_data["spr_connected"]:
            warnings.append("[WARN] SPR device not connected")

        if not self._status_data["knx_connected"]:
            warnings.append("[WARN] KNX system not connected")

        if not self._status_data["pump_connected"]:
            warnings.append("[WARN] Pump not connected")

        # Check system status
        if self._status_data["sensor"] == "Poor":
            warnings.append("[WARN] Sensor status: Poor - Check sensor calibration")
        elif self._status_data["sensor"] == "Caution":
            warnings.append("⚡ Sensor status: Caution - Monitor sensor performance")

        if self._status_data["optics"] == "Poor":
            warnings.append("[WARN] Optics status: Poor - Check optical alignment")
        elif self._status_data["optics"] == "Caution":
            warnings.append("⚡ Optics status: Caution - Monitor optical performance")

        if self._status_data["fluidics"] == "Poor":
            warnings.append("[WARN] Fluidics status: Poor - Check flow system")
        elif self._status_data["fluidics"] == "Caution":
            warnings.append("⚡ Fluidics status: Caution - Monitor flow system")

        # Determine message style and content
        if warnings:
            # Determine severity
            has_critical = any(
                "Poor" in str(w) or "not connected" in str(w) for w in warnings
            )

            if has_critical:
                # Red/error style for critical issues
                self.status_container.setStyleSheet(
                    "QFrame#status_container {"
                    "    background-color: rgb(255, 235, 238);"
                    "    border: 1px solid rgb(244, 67, 54);"
                    "    border-radius: 8px;"
                    "    padding: 12px;"
                    "}",
                )
                self.title_label.setStyleSheet(
                    "color: rgb(183, 28, 28); background: transparent; border: none;",
                )
                self.message_label.setStyleSheet(
                    "color: rgb(183, 28, 28); background: transparent; border: none;",
                )
            else:
                # Yellow/warning style for caution issues
                self.status_container.setStyleSheet(
                    "QFrame#status_container {"
                    "    background-color: rgb(255, 243, 205);"
                    "    border: 1px solid rgb(255, 193, 7);"
                    "    border-radius: 8px;"
                    "    padding: 12px;"
                    "}",
                )
                self.title_label.setStyleSheet(
                    "color: rgb(102, 77, 3); background: transparent; border: none;",
                )
                self.message_label.setStyleSheet(
                    "color: rgb(102, 77, 3); background: transparent; border: none;",
                )

            message = "\n".join(warnings)
            self.message_label.setText(message)
            self.status_container.show()
        # All good - show green success message
        elif self._status_data["spr_connected"]:
            self.status_container.setStyleSheet(
                "QFrame#status_container {"
                "    background-color: rgb(232, 245, 233);"
                "    border: 1px solid rgb(46, 227, 111);"
                "    border-radius: 8px;"
                "    padding: 12px;"
                "}",
            )
            self.title_label.setStyleSheet(
                "color: rgb(27, 94, 32); background: transparent; border: none;",
            )
            self.message_label.setStyleSheet(
                "color: rgb(27, 94, 32); background: transparent; border: none;",
            )
            self.message_label.setText("✓ All systems operational")
            self.status_container.show()
        else:
            # Hide when no connection yet
            self.status_container.hide()
