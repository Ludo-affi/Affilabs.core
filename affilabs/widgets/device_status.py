"""Device Status Widget - Modern grayscale theme matching prototype."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Signal, Slot, Qt
from affilabs.utils.logger import logger


class DeviceStatusWidget(QWidget):
    """Widget displaying device connection status and system capacity (Prototype design)."""

    connect_requested = Signal()  # Emitted when user clicks Scan button
    device_status_changed = Signal(bool, bool, bool)  # SPR, KNX, Pump connection status
    system_status_changed = Signal(str, str, str)  # Sensor, Optics, Fluidics status

    # Controller type constants
    STATIC_CONTROLLERS = ['P4SPR', 'PicoP4SPR']
    FLOW_CONTROLLERS = ['PicoKNX2', 'PicoEZSPR', 'EZSPR']

    def __init__(self, parent=None):
        super(DeviceStatusWidget, self).__init__(parent)
        self._setup_ui()

        # Initialize with disconnected state
        self.update_status('', '', False)
        self.show()

    def _setup_ui(self):
        """Setup the Device Status UI matching prototype."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Section 1: Hardware Connected
        hw_section = QLabel("HARDWARE CONNECTED")
        hw_section.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 700;"
            "color: #86868B;"
            "background: transparent;"
            "letter-spacing: 0.5px;"
            "margin-left: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        main_layout.addWidget(hw_section)

        main_layout.addSpacing(8)

        # Card container for hardware section
        hw_card = QFrame()
        hw_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 8px;"
            "}"
        )
        hw_card_layout = QVBoxLayout(hw_card)
        hw_card_layout.setContentsMargins(12, 12, 12, 12)
        hw_card_layout.setSpacing(6)

        # Container for connected devices (max 3)
        self.hw_device_labels = []
        for i in range(3):
            device_label = QLabel(f"• Device {i+1}: Not connected")
            device_label.setStyleSheet(
                "font-size: 13px;"
                "color: #34C759;"
                "background: transparent;"
                "padding: 4px 0px;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            device_label.setVisible(False)  # Hidden by default
            hw_card_layout.addWidget(device_label)
            self.hw_device_labels.append(device_label)

        # No devices message
        self.hw_no_devices = QLabel("No hardware detected")
        self.hw_no_devices.setStyleSheet(
            "font-size: 13px;"
            "color: #86868B;"
            "background: transparent;"
            "padding: 8px 0px;"
            "font-style: italic;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        hw_card_layout.addWidget(self.hw_no_devices)

        hw_card_layout.addSpacing(4)

        # Scan button
        self.scan_btn = QPushButton("[SEARCH] Scan for Hardware")
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.setFixedHeight(36)
        self.scan_btn.clicked.connect(self._on_connect_clicked)
        self.scan_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 0px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  text-align: center;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}"
        )
        hw_card_layout.addWidget(self.scan_btn)

        main_layout.addWidget(hw_card)

        main_layout.addSpacing(16)

        # Section 2: Subunit Readiness
        subunit_section = QLabel("SUBUNIT READINESS")
        subunit_section.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 700;"
            "color: #86868B;"
            "background: transparent;"
            "letter-spacing: 0.5px;"
            "margin-left: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        main_layout.addWidget(subunit_section)

        main_layout.addSpacing(8)

        # Card container for subunits
        subunit_card = QFrame()
        subunit_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 8px;"
            "}"
        )
        subunit_card_layout = QVBoxLayout(subunit_card)
        subunit_card_layout.setContentsMargins(12, 10, 12, 10)
        subunit_card_layout.setSpacing(8)

        # Three subunits: Sensor, Optics, Fluidics
        self.subunit_status = {}
        subunit_names = ["Sensor", "Optics", "Fluidics"]

        for i, subunit_name in enumerate(subunit_names):
            # Container for each subunit
            subunit_row = QHBoxLayout()
            subunit_row.setSpacing(10)
            subunit_row.setContentsMargins(0, 0, 0, 0)

            # Status indicator (circle)
            status_indicator = QLabel("●")
            status_indicator.setFixedWidth(12)
            status_indicator.setStyleSheet(
                "font-size: 14px;"
                "color: #86868B;"  # Gray for not ready
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            subunit_row.addWidget(status_indicator)

            # Subunit name
            name_label = QLabel(subunit_name)
            name_label.setStyleSheet(
                "font-size: 13px;"
                "color: #1D1D1F;"
                "background: transparent;"
                "font-weight: 500;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            subunit_row.addWidget(name_label)

            subunit_row.addStretch()

            # Status text
            status_label = QLabel("Not Ready")
            status_label.setStyleSheet(
                "font-size: 12px;"
                "color: #86868B;"
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            subunit_row.addWidget(status_label)

            # Store references
            self.subunit_status[subunit_name] = {
                'indicator': status_indicator,
                'status_label': status_label
            }

            # Add to card layout
            subunit_container = QWidget()
            subunit_container.setLayout(subunit_row)
            subunit_card_layout.addWidget(subunit_container)

            # Add separator between items (not after last)
            if i < len(subunit_names) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.06);"
                    "max-height: 1px;"
                    "margin: 4px 0px;"
                )
                subunit_card_layout.addWidget(separator)

        main_layout.addWidget(subunit_card)

        main_layout.addSpacing(16)

        # Section 3: Operation Modes
        mode_section = QLabel("OPERATION MODES")
        mode_section.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 700;"
            "color: #86868B;"
            "background: transparent;"
            "letter-spacing: 0.5px;"
            "margin-left: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        main_layout.addWidget(mode_section)

        main_layout.addSpacing(8)

        # Card container for operation modes
        mode_card = QFrame()
        mode_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 8px;"
            "}"
        )
        mode_card_layout = QVBoxLayout(mode_card)
        mode_card_layout.setContentsMargins(12, 10, 12, 10)
        mode_card_layout.setSpacing(8)

        # Operation Modes
        self.operation_modes = {}
        mode_names = ["Static", "Flow"]

        for i, mode_name in enumerate(mode_names):
            # Container for each mode
            mode_row = QHBoxLayout()
            mode_row.setSpacing(10)
            mode_row.setContentsMargins(0, 0, 0, 0)

            # Status indicator (circle)
            mode_indicator = QLabel("●")
            mode_indicator.setFixedWidth(12)
            mode_indicator.setStyleSheet(
                "font-size: 14px;"
                "color: #86868B;"  # Gray for disabled
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            mode_row.addWidget(mode_indicator)

            # Mode name
            mode_label = QLabel(mode_name)
            mode_label.setStyleSheet(
                "font-size: 13px;"
                "color: #1D1D1F;"
                "background: transparent;"
                "font-weight: 500;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            mode_row.addWidget(mode_label)

            mode_row.addStretch()

            # Status text
            mode_status_label = QLabel("Disabled")
            mode_status_label.setStyleSheet(
                "font-size: 12px;"
                "color: #86868B;"
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            mode_row.addWidget(mode_status_label)

            # Store references
            self.operation_modes[mode_name] = {
                'indicator': mode_indicator,
                'status_label': mode_status_label
            }

            # Add to card layout
            mode_container = QWidget()
            mode_container.setLayout(mode_row)
            mode_card_layout.addWidget(mode_container)

            # Add separator between items (not after last)
            if i < len(mode_names) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.06);"
                    "max-height: 1px;"
                    "margin: 4px 0px;"
                )
                mode_card_layout.addWidget(separator)

        main_layout.addWidget(mode_card)

        main_layout.addSpacing(16)

        # Section 4: LED Status (V1.1+ firmware)
        led_section = QLabel("LED STATUS")
        led_section.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 700;"
            "color: #86868B;"
            "background: transparent;"
            "letter-spacing: 0.5px;"
            "margin-left: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        main_layout.addWidget(led_section)

        main_layout.addSpacing(8)

        # Card container for LED status
        self.led_status_card = QFrame()
        self.led_status_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 8px;"
            "}"
        )
        led_card_layout = QVBoxLayout(self.led_status_card)
        led_card_layout.setContentsMargins(12, 10, 12, 10)
        led_card_layout.setSpacing(8)

        # LED channels: A, B, C, D
        self.led_status = {}
        led_channels = ["A", "B", "C", "D"]

        for i, channel in enumerate(led_channels):
            # Container for each LED
            led_row = QHBoxLayout()
            led_row.setSpacing(10)
            led_row.setContentsMargins(0, 0, 0, 0)

            # Status indicator (circle)
            status_indicator = QLabel("●")
            status_indicator.setFixedWidth(12)
            status_indicator.setStyleSheet(
                "font-size: 14px;"
                "color: #86868B;"  # Gray for off
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            led_row.addWidget(status_indicator)

            # LED name
            name_label = QLabel(f"LED {channel}")
            name_label.setStyleSheet(
                "font-size: 13px;"
                "color: #1D1D1F;"
                "background: transparent;"
                "font-weight: 500;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            led_row.addWidget(name_label)

            led_row.addStretch()

            # Intensity value
            intensity_label = QLabel("0")
            intensity_label.setStyleSheet(
                "font-size: 12px;"
                "color: #86868B;"
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            led_row.addWidget(intensity_label)

            # Store references
            self.led_status[channel] = {
                'indicator': status_indicator,
                'intensity_label': intensity_label
            }

            # Add to card layout
            led_container = QWidget()
            led_container.setLayout(led_row)
            led_card_layout.addWidget(led_container)

            # Add separator between items (not after last)
            if i < len(led_channels) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.06);"
                    "max-height: 1px;"
                    "margin: 4px 0px;"
                )
                led_card_layout.addWidget(separator)

        main_layout.addWidget(self.led_status_card)

        # Hide LED status by default (shown when V1.1+ firmware detected)
        self.led_status_card.setVisible(False)

        main_layout.addStretch()

    @Slot()
    def _on_connect_clicked(self):
        """Handle scan button click."""
        self.connect_requested.emit()

    def update_status(self, ctrl_type: str, knx_type: str, pump_connected: bool):
        """
        Update the device status display.

        Args:
            ctrl_type: Controller type string ('P4SPR', 'PicoP4SPR', 'EZSPR', 'PicoEZSPR', etc.)
            knx_type: Kinetic controller type string ('KNX', 'KNX2', 'PicoKNX2', etc.)
            pump_connected: Whether a pump is connected (True/False/None)
        """
        # Determine if devices are connected
        spr_connected = bool(ctrl_type and ctrl_type != '')
        knx_connected = bool(knx_type and knx_type != '')

        # Update Hardware Connected section
        device_count = 0
        if spr_connected:
            self.hw_device_labels[device_count].setText(f"• SPR Controller: {ctrl_type}")
            self.hw_device_labels[device_count].setVisible(True)
            device_count += 1

        if knx_connected:
            self.hw_device_labels[device_count].setText(f"• Kinetic Controller: {knx_type}")
            self.hw_device_labels[device_count].setVisible(True)
            device_count += 1

        if pump_connected:
            self.hw_device_labels[device_count].setText("• Pump: Connected")
            self.hw_device_labels[device_count].setVisible(True)
            device_count += 1

        # Hide unused device labels
        for i in range(device_count, 3):
            self.hw_device_labels[i].setVisible(False)

        # Show/hide no devices message
        self.hw_no_devices.setVisible(device_count == 0)

        # Update scan button text based on connection status
        if device_count > 0:
            self.scan_btn.setText("✓ Hardware Connected")
        else:
            self.scan_btn.setText("[SEARCH] Scan for Hardware")

        # Determine system capacity based on controller type
        capacity = self._determine_capacity(ctrl_type, knx_type)

        # Update Operation Modes
        for mode_name, mode_widgets in self.operation_modes.items():
            if capacity == mode_name:
                # Active mode - green indicator
                mode_widgets['indicator'].setStyleSheet(
                    "font-size: 14px;"
                    "color: #34C759;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                mode_widgets['status_label'].setText("Enabled")
                mode_widgets['status_label'].setStyleSheet(
                    "font-size: 12px;"
                    "color: #34C759;"
                    "background: transparent;"
                    "font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
            else:
                # Inactive mode - gray indicator
                mode_widgets['indicator'].setStyleSheet(
                    "font-size: 14px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                mode_widgets['status_label'].setText("Disabled")
                mode_widgets['status_label'].setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

        # Emit device status change signal
        self.device_status_changed.emit(spr_connected, knx_connected, pump_connected)

        logger.debug(f"Device status updated: SPR={ctrl_type}, KNX={knx_type}, Pump={pump_connected}, Capacity={capacity}")

    def _determine_capacity(self, ctrl_type: str, knx_type: str) -> str:
        """
        Determine system capacity based on connected controllers.

        Logic:
        - Arduino or PicoP4SPR → Static only
        - PicoKNX or PicoEZSPR (with kinetics) → Flow
        - No controller → Unknown

        Args:
            ctrl_type: Controller type string
            knx_type: Kinetic controller type string

        Returns:
            Capacity string: "Static", "Flow", or "Unknown"
        """
        if not ctrl_type:
            return "Unknown"

        # Check if Flow-capable (PicoKNX2, PicoEZSPR, EZSPR)
        if ctrl_type in self.FLOW_CONTROLLERS:
            return "Flow"

        # Check if kinetic device is connected to enable Flow
        if knx_type and knx_type in ['KNX', 'KNX2', 'PicoKNX2']:
            return "Flow"

        # Check if Static-only controllers
        if ctrl_type in self.STATIC_CONTROLLERS:
            return "Static"

        return "Unknown"

    def update_system_status(self, sensor_status: str = "Unknown", optics_status: str = "Unknown", fluidics_status: str = "Unknown"):
        """
        Update the system status indicators (Subunit Readiness).

        Args:
            sensor_status: Status for Sensor ("Ready", "Caution", "Error", "Not Ready")
            optics_status: Status for Optics ("Ready", "Caution", "Error", "Not Ready")
            fluidics_status: Status for Fluidics ("Ready", "Caution", "Error", "Not Ready")
        """
        # Status color mapping
        status_colors = {
            "Ready": "#34C759",           # Green
            "Caution": "#FFCC00",         # Yellow
            "Error": "#FF3B30",           # Red
            "Not Ready": "#86868B"        # Gray
        }

        # Status label weight mapping
        status_weights = {
            "Ready": "600",
            "Caution": "600",
            "Error": "600",
            "Not Ready": "400"
        }

        # Update Sensor
        if "Sensor" in self.subunit_status:
            color = status_colors.get(sensor_status, status_colors["Not Ready"])
            weight = status_weights.get(sensor_status, "400")
            self.subunit_status["Sensor"]['indicator'].setStyleSheet(
                f"font-size: 14px; color: {color}; background: transparent; "
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            self.subunit_status["Sensor"]['status_label'].setText(sensor_status)
            self.subunit_status["Sensor"]['status_label'].setStyleSheet(
                f"font-size: 12px; color: {color}; background: transparent; font-weight: {weight}; "
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

        # Update Optics
        if "Optics" in self.subunit_status:
            color = status_colors.get(optics_status, status_colors["Not Ready"])
            weight = status_weights.get(optics_status, "400")
            self.subunit_status["Optics"]['indicator'].setStyleSheet(
                f"font-size: 14px; color: {color}; background: transparent; "
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            self.subunit_status["Optics"]['status_label'].setText(optics_status)
            self.subunit_status["Optics"]['status_label'].setStyleSheet(
                f"font-size: 12px; color: {color}; background: transparent; font-weight: {weight}; "
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

        # Update Fluidics
        if "Fluidics" in self.subunit_status:
            color = status_colors.get(fluidics_status, status_colors["Not Ready"])
            weight = status_weights.get(fluidics_status, "400")
            self.subunit_status["Fluidics"]['indicator'].setStyleSheet(
                f"font-size: 14px; color: {color}; background: transparent; "
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            self.subunit_status["Fluidics"]['status_label'].setText(fluidics_status)
            self.subunit_status["Fluidics"]['status_label'].setStyleSheet(
                f"font-size: 12px; color: {color}; background: transparent; font-weight: {weight}; "
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
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

    def update_led_status(self, led_intensities: dict):
        """Update LED status display (V1.1+ firmware).

        Args:
            led_intensities: Dict with keys 'a', 'b', 'c', 'd' and intensity values 0-255
                            or None to hide LED status
        """
        if led_intensities is None:
            # Hide LED status section (firmware doesn't support it)
            self.led_status_card.setVisible(False)
            return

        # Show LED status section
        self.led_status_card.setVisible(True)

        # Update each LED channel
        for channel_lower, intensity in led_intensities.items():
            channel_upper = channel_lower.upper()
            if channel_upper in self.led_status:
                # Update intensity label
                self.led_status[channel_upper]['intensity_label'].setText(str(intensity))

                # Update indicator color based on intensity
                if intensity > 0:
                    # LED is ON - use green with brightness based on intensity
                    alpha = int((intensity / 255) * 100) + 30  # 30-130% brightness
                    color = f"rgba(52, 199, 89, {min(alpha, 100)/100})"  # Green
                else:
                    # LED is OFF - gray
                    color = "#86868B"

                self.led_status[channel_upper]['indicator'].setStyleSheet(
                    f"font-size: 14px; color: {color}; background: transparent; "
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

                # Update intensity label color
                intensity_color = "#34C759" if intensity > 0 else "#86868B"
                self.led_status[channel_upper]['intensity_label'].setStyleSheet(
                    f"font-size: 12px; color: {intensity_color}; background: transparent; "
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

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
