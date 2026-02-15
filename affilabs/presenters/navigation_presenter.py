"""Navigation Presenter

Manages navigation bar creation, page switching, and button state management.
Extracted from affilabs_core_ui.py for better modularity.
"""

from pathlib import Path

from affilabs.utils.resource_path import get_affilabs_resource, get_resource_path
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
from ui_styles import Colors, Fonts, label_style


class NavigationPresenter:
    """Presents navigation bar and handles page switching logic."""

    def __init__(self, main_window):
        """Initialize the navigation presenter.

        Args:
            main_window: Reference to the main window (AffilabsMainWindow)

        """
        self.main_window = main_window
        self.nav_buttons: list[QPushButton] = []

    def create_navigation_bar(self) -> QWidget:
        """Create the pill-shaped navigation bar with control buttons.

        Returns:
            QWidget containing the complete navigation bar

        """
        nav_widget = QWidget()
        nav_widget.setStyleSheet("QWidget { background: #FFFFFF; }")
        nav_widget.setFixedHeight(60)

        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(20, 10, 20, 10)
        nav_layout.setSpacing(12)

        # Navigation buttons (Analysis and Report tabs disabled)
        nav_button_configs = [
            ("Live", 0, "Real-time data visualization and cycle monitoring"),
            ("Edits", 1, "Edit and annotate experiment data"),
        ]

        for i, (label, page_index, tooltip) in enumerate(nav_button_configs):
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            btn.setMinimumWidth(120)
            btn.setCheckable(True)
            btn.setChecked(i == 0)  # First button selected by default
            btn.setToolTip(tooltip)

            # Store button reference
            self.nav_buttons.append(btn)

            # Update style based on checked state
            btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(46, 48, 227, 0.1);"
                "  color: rgb(46, 48, 227);"
                "  border: none;"
                "  border-radius: 20px;"
                "  padding: 8px 24px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(46, 48, 227, 0.2);"
                "}"
                "QPushButton:checked {"
                "  background: rgba(46, 48, 227, 1.0);"
                "  color: white;"
                "  font-weight: 600;"
                "}",
            )

            # Connect to switch page
            btn.clicked.connect(lambda checked, idx=page_index: self.switch_page(idx))

            nav_layout.addWidget(btn)

        nav_layout.addStretch()

        # Add 16px separation before control buttons
        nav_layout.addSpacing(16)

        # Recording status indicator (next to record button)
        self.main_window.recording_indicator = QFrame()
        self.main_window.recording_indicator.setFixedSize(200, 32)
        indicator_layout = QHBoxLayout(self.main_window.recording_indicator)
        indicator_layout.setContentsMargins(10, 6, 10, 6)
        indicator_layout.setSpacing(8)

        self.main_window.rec_status_dot = QLabel("●")
        self.main_window.rec_status_dot.setStyleSheet(
            "QLabel {"
            "  color: #86868B;"
            "  font-size: 16px;"
            "  background: transparent;"
            "}",
        )
        indicator_layout.addWidget(self.main_window.rec_status_dot)

        # Removed static status text - now shown as tooltip on record button
        indicator_layout.addStretch()

        self.main_window.recording_indicator.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.04);  border-radius: 16px;  }",
        )
        # Hide recording indicator box (keep for internal use but don't display)
        self.main_window.recording_indicator.setVisible(False)

        nav_layout.addSpacing(8)

        # Timer button
        self._create_timer_button(nav_layout)

        nav_layout.addSpacing(4)

        # Pause button
        self._create_pause_button(nav_layout)

        nav_layout.addSpacing(4)

        # Record button
        self._create_record_button(nav_layout)

        nav_layout.addSpacing(40)  # Larger gap before power button

        # Power button
        self._create_power_button(nav_layout)

        # Connecting overlay (hidden until connecting) - will be positioned over main content
        self.main_window.connecting_label = QLabel("Connecting to hardware...")
        self.main_window.connecting_label.setVisible(False)
        self.main_window.connecting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_window.connecting_label.setStyleSheet(
            "QLabel {"
            "  color: #1D1D1F;"
            "  background: rgba(255, 255, 255, 0.95);"
            "  font-size: 14px;"
            "  font-weight: 600;"
            "  padding: 16px 32px;"
            "  border: 2px solid #E6B800;"
            "  border-radius: 12px;"
            "}",
        )
        # Don't add to nav_layout - will be positioned as overlay in show_connecting_indicator

        nav_layout.addSpacing(16)  # Space between power button and logo

        # Company logo
        self._create_company_logo(nav_layout)

        return nav_widget

    def _create_timer_button(self, layout):
        """Create timer button with matching styling to pause/record buttons."""
        from affilabs.widgets.timer_button import TimerButton

        self.main_window.timer_button = TimerButton(parent=self.main_window)
        self.main_window.timer_button.setFixedSize(36, 36)
        self.main_window.timer_button.set_compact_mode(True)  # Icon-only mode
        self.main_window.timer_button.setToolTip(
            "Manual Timer\n"
            "Set a manual countdown timer for experimental protocols\n"
            "(Click to open timer popup)",
        )

        # Style to match pause/record buttons
        self.main_window.timer_button.setStyleSheet(
            "QPushButton {"
            "  background: rgba(46, 48, 227, 0.1);"
            "  border: 1px solid rgba(46, 48, 227, 0.3);"
            "  border-radius: 8px;"
            "  font-size: 16px;"
            "  text-align: center;"
            "  padding: 0px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(46, 48, 227, 0.15);"
            "  border: 1px solid rgba(46, 48, 227, 0.4);"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(46, 48, 227, 0.25);"
            "}"
        )

        self.main_window.timer_button.clicked.connect(self.main_window._on_timer_button_clicked)
        self.main_window.timer_button.clear_requested.connect(self.main_window._on_clear_manual_timer)
        self.main_window.timer_button.restart_requested.connect(self.main_window._on_restart_manual_timer)
        layout.addWidget(self.main_window.timer_button)

    def _create_pause_button(self, layout):
        """Create pause button with SVG icon."""
        self.main_window.pause_btn = QPushButton()
        self.main_window.pause_btn.setCheckable(True)
        self.main_window.pause_btn.setFixedSize(36, 36)
        self.main_window.pause_btn.setEnabled(
            False,
        )  # Disabled until acquisition starts
        self.main_window.pause_btn.setToolTip(
            "Pause Live Acquisition\n(Enabled after calibration)",
        )
        self.main_window.pause_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(46, 48, 227, 0.1);"
            "  border: 1px solid rgba(46, 48, 227, 0.3);"
            "  border-radius: 8px;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(46, 48, 227, 0.15);"
            "  border: 1px solid rgba(46, 48, 227, 0.4);"
            "}"
            "QPushButton:checked {"
            "  background: #FF9500;"
            "  border: 1px solid rgba(255, 149, 0, 0.3);"
            "}"
            "QPushButton:hover:checked {"
            "  background: #E68500;"
            "  border: 1px solid rgba(230, 133, 0, 0.3);"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(46, 48, 227, 0.1);"
            "  border: 1px solid rgba(46, 48, 227, 0.1);"
            "}",
        )

        # Use SVG icon — load directly like timer/power buttons
        pause_svg = get_resource_path("ui/img/pause_icon.svg")
        pause_white_svg = get_resource_path("ui/img/pause_icon_white.svg")
        if pause_svg.exists():
            icon = QIcon(str(pause_svg))
            # Add white variant for checked (On) state
            if pause_white_svg.exists():
                icon.addFile(str(pause_white_svg), QSize(), QIcon.Mode.Normal, QIcon.State.On)
            # Also register for disabled state so Qt doesn't blank it
            icon.addFile(str(pause_svg), QSize(), QIcon.Mode.Disabled, QIcon.State.Off)
            self.main_window.pause_btn.setIcon(icon)
            self.main_window.pause_btn.setIconSize(QSize(20, 20))

        self.main_window.pause_btn.clicked.connect(self.main_window._toggle_pause)
        layout.addWidget(self.main_window.pause_btn)

    def _create_record_button(self, layout):
        """Create record button."""
        self.main_window.record_btn = QPushButton()
        self.main_window.record_btn.setCheckable(True)
        self.main_window.record_btn.setFixedSize(36, 36)
        self.main_window.record_btn.setEnabled(
            False,
        )  # Disabled until acquisition starts
        self.main_window.record_btn.setToolTip(
            "Start Recording\n(Enabled after calibration)",
        )
        self.main_window.record_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(46, 48, 227, 0.1);"
            "  border: 1px solid rgba(46, 48, 227, 0.3);"
            "  border-radius: 8px;"
            "  padding: 0px;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(46, 48, 227, 0.15);"
            "  border: 1px solid rgba(46, 48, 227, 0.4);"
            "}"
            "QPushButton:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1;"
            "  border: 1px solid rgba(255, 59, 48, 0.3);"
            "}"
            "QPushButton:hover:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1;"
            "  border: 1px solid rgba(230, 52, 42, 0.3);"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(46, 48, 227, 0.1);"
            "  border: 1px solid rgba(46, 48, 227, 0.1);"
            "}",
        )

        # Use SVG icon — load directly like timer/power buttons
        record_svg = get_resource_path("ui/img/record_icon.svg")
        record_white_svg = get_resource_path("ui/img/record_icon_white.svg")
        if record_svg.exists():
            icon = QIcon(str(record_svg))
            # Add white variant for checked (On) state
            if record_white_svg.exists():
                icon.addFile(str(record_white_svg), QSize(), QIcon.Mode.Normal, QIcon.State.On)
            # Also register for disabled state so Qt doesn't blank it
            icon.addFile(str(record_svg), QSize(), QIcon.Mode.Disabled, QIcon.State.Off)
            self.main_window.record_btn.setIcon(icon)
            self.main_window.record_btn.setIconSize(QSize(20, 20))

        self.main_window.record_btn.clicked.connect(self.main_window._toggle_recording)
        layout.addWidget(self.main_window.record_btn)

    def _create_power_button(self, layout):
        """Create power button with state management."""
        self.main_window.power_btn = QPushButton()
        self.main_window.power_btn.setFixedSize(36, 36)
        self.main_window.power_btn.setProperty("powerState", "disconnected")

        # Use SVG icon instead of emoji text
        power_svg = get_resource_path("ui/img/power_icon.svg")
        if power_svg.exists():
            self.main_window.power_btn.setIcon(QIcon(str(power_svg)))
            self.main_window.power_btn.setIconSize(QSize(24, 24))
        else:
            self.main_window.power_btn.setText("⏻")  # Emoji fallback

        # Apply original stylesheet with state-based coloring
        self.main_window.power_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(29, 29, 31, 0.4), stop:1 rgba(29, 29, 31, 0.5));"
            "  color: white;"
            "  border: 1px solid rgba(29, 29, 31, 0.2);"
            "  border-radius: 18px;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(29, 29, 31, 0.5), stop:1 rgba(29, 29, 31, 0.6));"
            "  border: 1px solid rgba(29, 29, 31, 0.3);"
            "}",
        )

        self.main_window._update_power_button_style()
        self.main_window.power_btn.setToolTip(
            "Power On Device (Ctrl+P)\n"
            "Gray = Disconnected | Yellow = Searching | Green = Connected",
        )
        self.main_window.power_btn.clicked.connect(self.main_window._handle_power_click)
        layout.addWidget(self.main_window.power_btn)

    def _create_company_logo(self, layout):
        """Create company logo label."""
        logo_label = QLabel()
        # Load logo using resource path helper (works in frozen exe)
        logo_path = get_affilabs_resource("ui/img/affinite-no-background.png")

        if logo_path.exists():
            logo_pixmap = QPixmap(str(logo_path))
            if not logo_pixmap.isNull():
                # Scale logo to larger size while maintaining aspect ratio
                scaled_logo = logo_pixmap.scaledToHeight(
                    40,
                    Qt.TransformationMode.SmoothTransformation,
                )
                logo_label.setPixmap(scaled_logo)
                # Debug: Add border to see logo position
                logo_label.setStyleSheet("border: 2px solid red; background: white;")
            else:
                # Fallback if pixmap failed
                logo_label.setText("Affinité")
                logo_label.setStyleSheet(
                    "font-size: 16px; font-weight: bold; color: #1D1D1F;",
                )
        else:
            # Fallback if file not found
            logo_label.setText("Affinité")
            logo_label.setStyleSheet(
                "font-size: 16px; font-weight: bold; color: #1D1D1F;",
            )
        logo_label.setStyleSheet("background: transparent;")
        logo_label.setToolTip("Affinité Instruments")
        layout.addWidget(logo_label)

    def switch_page(self, page_index: int) -> None:
        """Switch to the selected page and update button states.

        Args:
            page_index: Index of the page to switch to (0-3)

        """
        self.main_window.content_stack.setCurrentIndex(page_index)

        # Update button checked states (radio button behavior)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == page_index)

        # Hide sidebar when switching to Edits tab (index 1), show for all others
        if hasattr(self.main_window, 'sidebar'):
            if page_index == 1:  # Edits tab
                self.main_window.sidebar.hide()
            else:
                self.main_window.sidebar.show()

    def get_buttons(self) -> list[QPushButton]:
        """Get the list of navigation buttons.

        Returns:
            List of navigation QPushButton instances

        """
        return self.nav_buttons
