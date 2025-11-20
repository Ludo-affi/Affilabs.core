"""Device Status Widget - Shows connection status and system capacity."""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, Slot

from ui.ui_device_status import Ui_DeviceStatus
from utils.logger import logger


class DeviceStatusWidget(QWidget):
    """Widget displaying device connection status and system capacity."""

    connect_requested = Signal()  # Emitted when user clicks Connect button
    device_status_changed = Signal(bool, bool, bool)  # SPR, KNX, Pump connection status
    system_status_changed = Signal(str, str, str)  # Sensor, Optics, Fluidics status

    # Controller type constants
    STATIC_CONTROLLERS = ['P4SPR', 'PicoP4SPR']
    FLOW_CONTROLLERS = ['PicoKNX2', 'PicoEZSPR', 'EZSPR']
    QSPR_CONTROLLERS = ['QSPR']

    def __init__(self, parent=None):
        super(DeviceStatusWidget, self).__init__(parent)
        self.ui = Ui_DeviceStatus()
        self.ui.setupUi(self)

        # Connect signals
        self.ui.spr_connect_btn.clicked.connect(self._on_connect_clicked)

        # Initialize with disconnected state and ensure visible
        self.update_status('', '', False)
        self.show()  # Always show by default

    @Slot()
    def _on_connect_clicked(self):
        """Handle connect button click."""
        self.connect_requested.emit()

    def update_status(self, ctrl_type: str, knx_type: str, pump_connected: bool):
        """
        Update the device status display.

        Args:
            ctrl_type: Controller type string ('P4SPR', 'PicoP4SPR', 'QSPR', 'EZSPR', 'PicoEZSPR', etc.)
            knx_type: Kinetic controller type string ('KNX', 'KNX2', 'PicoKNX2', etc.)
            pump_connected: Whether a pump is connected (True/False/None)
        """
        # Determine if SPR device is connected
        spr_connected = bool(ctrl_type and ctrl_type != '')

        # Update SPR device status with green light when connected
        if spr_connected:
            self.ui.spr_device_status.setText("Connected")
            self.ui.spr_device_indicator.setStyleSheet(
                "QLabel { background-color: rgb(46, 227, 111); border-radius: 5px; }"
            )
            self.ui.spr_connect_btn.hide()
        else:
            self.ui.spr_device_status.setText("Not Connected")
            self.ui.spr_device_indicator.setStyleSheet(
                "QLabel { background-color: rgb(200, 200, 200); border-radius: 5px; }"
            )
            self.ui.spr_connect_btn.show()

        # Update Pump status
        if pump_connected:
            self.ui.pump_status.setText("Connected")
            self.ui.pump_indicator.setStyleSheet(
                "QLabel { background-color: rgb(46, 227, 111); border-radius: 5px; }"
            )
        else:
            self.ui.pump_status.setText("Not Connected")
            self.ui.pump_indicator.setStyleSheet(
                "QLabel { background-color: rgb(200, 200, 200); border-radius: 5px; }"
            )

        # Determine system capacity based on controller type
        capacity = self._determine_capacity(ctrl_type, knx_type)

        # Update operation mode display
        # Style for inactive mode (gray, normal weight)
        inactive_style = (
            "QLabel { "
            "color: rgb(100, 100, 100); "
            "background-color: transparent; "
            "padding: 3px 8px; "
            "border-radius: 3px; "
            "}"
        )

        # Style for active mode (white text on blue background, bold)
        active_style = (
            "QLabel { "
            "color: white; "
            "background-color: rgb(46, 48, 227); "
            "padding: 3px 8px; "
            "border-radius: 3px; "
            "font-weight: bold; "
            "}"
        )

        # Reset all modes to inactive
        self.ui.static_mode_label.setStyleSheet(inactive_style)
        self.ui.flow_mode_label.setStyleSheet(inactive_style)
        self.ui.not_supported_label.setStyleSheet(inactive_style)

        # Highlight active mode and show/hide Not Supported
        if capacity == "Static":
            self.ui.static_mode_label.setStyleSheet(active_style)
            self.ui.not_supported_label.setVisible(False)
        elif capacity == "Flow":
            self.ui.flow_mode_label.setStyleSheet(active_style)
            self.ui.not_supported_label.setVisible(False)
        elif capacity == "Not Supported":
            self.ui.not_supported_label.setStyleSheet(active_style)
            self.ui.not_supported_label.setVisible(True)
        else:
            # If Unknown, hide Not Supported and all stay inactive (gray)
            self.ui.not_supported_label.setVisible(False)

        # Always show the widget (even when not connected, to show status)
        self.show()

        # Emit device status change signal
        knx_connected = bool(knx_type and knx_type != '')
        self.device_status_changed.emit(spr_connected, knx_connected, pump_connected)

        logger.debug(f"Device status updated: SPR={ctrl_type}, KNX={knx_type}, Pump={pump_connected}, Capacity={capacity}")

    def _determine_capacity(self, ctrl_type: str, knx_type: str) -> str:
        """
        Determine system capacity based on connected controllers.

        Logic:
        - Arduino or PicoP4SPR → Static only
        - PicoKNX or PicoEZSPR (with kinetics) → Flow
        - QSPR → Not Supported
        - No controller → Unknown

        Args:
            ctrl_type: Controller type string
            knx_type: Kinetic controller type string

        Returns:
            Capacity string: "Static", "Flow", "Not Supported", or "Unknown"
        """
        if not ctrl_type:
            return "Unknown"

        # Check if QSPR (not supported)
        if ctrl_type in self.QSPR_CONTROLLERS:
            return "Not Supported"

        # Check if Flow-capable (PicoKNX2, PicoEZSPR, EZSPR)
        # These devices have kinetic capabilities built-in or use PicoKNX2
        if ctrl_type in self.FLOW_CONTROLLERS:
            return "Flow"

        # Check if kinetic device is connected to enable Flow
        if knx_type and knx_type in ['KNX', 'KNX2', 'PicoKNX2']:
            return "Flow"

        # Check if Static-only controllers (Arduino P4SPR, PicoP4SPR without kinetics)
        if ctrl_type in self.STATIC_CONTROLLERS:
            return "Static"

        # Default to Unknown if we can't determine
        return "Unknown"

    def update_system_status(self, sensor_status: str = "Unknown", optics_status: str = "Unknown", fluidics_status: str = "Unknown"):
        """
        Update the system status indicators.

        Args:
            sensor_status: Status for Sensor ("Good", "Caution", "Poor", "Unknown")
            optics_status: Status for Optics ("Good", "Caution", "Poor", "Unknown")
            fluidics_status: Status for Fluidics ("Good", "Caution", "Poor", "Unknown")
        """
        # Color mapping for status
        status_colors = {
            "Good": "rgb(46, 227, 111)",      # Green
            "Caution": "rgb(255, 193, 7)",    # Yellow
            "Poor": "rgb(244, 67, 54)",       # Red
            "Unknown": "rgb(200, 200, 200)"   # Gray
        }

        # Update Sensor
        self.ui.sensor_status_label.setText(sensor_status)
        self.ui.sensor_status_indicator.setStyleSheet(
            f"QLabel {{ background-color: {status_colors.get(sensor_status, status_colors['Unknown'])}; border-radius: 6px; }}"
        )

        # Update Optics
        self.ui.optics_status_label.setText(optics_status)
        self.ui.optics_status_indicator.setStyleSheet(
            f"QLabel {{ background-color: {status_colors.get(optics_status, status_colors['Unknown'])}; border-radius: 6px; }}"
        )

        # Update Fluidics
        self.ui.fluidics_status_label.setText(fluidics_status)
        self.ui.fluidics_status_indicator.setStyleSheet(
            f"QLabel {{ background-color: {status_colors.get(fluidics_status, status_colors['Unknown'])}; border-radius: 6px; }}"
        )

        # Emit system status change signal
        self.system_status_changed.emit(sensor_status, optics_status, fluidics_status)

        logger.debug(f"System status updated: Sensor={sensor_status}, Optics={optics_status}, Fluidics={fluidics_status}")

    def get_main_layout(self):
        """Return the main layout of the hardware status container for adding widgets."""
        return self.ui.main_layout

    def add_widget_to_layout(self, widget, position=-1):
        """
        Add a widget to the main hardware status layout.

        Args:
            widget: QWidget to add
            position: Position to insert (-1 for append at end, before spacer)
        """
        if position == -1:
            # Insert before the spacer at the bottom
            count = self.ui.main_layout.count()
            # Find spacer position
            for i in range(count):
                item = self.ui.main_layout.itemAt(i)
                if item.spacerItem():
                    self.ui.main_layout.insertWidget(i, widget)
                    return
            # If no spacer found, just add it
            self.ui.main_layout.addWidget(widget)
        else:
            self.ui.main_layout.insertWidget(position, widget)

    def get_connect_button(self):
        """Return the connect button for external manipulation."""
        return self.ui.spr_connect_btn

    def move_connect_button_to_layout(self, layout, position=-1):
        """
        Move the connect button from its current location to a different layout.

        Args:
            layout: QLayout to move the button to
            position: Position to insert (-1 for append)
        """
        # Remove button from current layout
        current_layout = self.ui.connect_btn_layout
        if current_layout:
            current_layout.removeWidget(self.ui.spr_connect_btn)

        # Add to new layout
        if position == -1:
            layout.addWidget(self.ui.spr_connect_btn)
        else:
            layout.insertWidget(position, self.ui.spr_connect_btn)

        self.ui.spr_connect_btn.setParent(layout.parentWidget() if hasattr(layout, 'parentWidget') else None)
