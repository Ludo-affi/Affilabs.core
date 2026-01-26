"""Navigation Presenter

Manages navigation bar creation, page switching, and button state management.
Extracted from affilabs_core_ui.py for better modularity.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
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
        nav_widget.setStyleSheet("background: #FFFFFF;")
        nav_widget.setFixedHeight(60)

        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(20, 10, 20, 10)
        nav_layout.setSpacing(12)

        # Navigation buttons
        nav_button_configs = [
            ("Live", 0, "Real-time data visualization and cycle monitoring"),
            ("Edits", 1, "Edit and annotate experiment data"),
            ("Analyze", 2, "Analyze results and generate reports"),
            ("Report", 3, "Export and share experiment reports"),
        ]

        for i, (label, page_index, tooltip) in enumerate(nav_button_configs):
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            btn.setMinimumWidth(120)
            btn.setCheckable(True)
            btn.setChecked(i == 0)  # First button selected by default
            btn.setToolTip(tooltip)

            # TEMPORARY: Hide Analyze and Report tabs (v1.0 focus on Sensorgram/Edits)
            if label in ["Analyze", "Report"]:
                btn.setVisible(False)

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

        # Recording timer (hidden by default, shows when recording)
        timer_label = QLabel("00:00:00")
        timer_label.setStyleSheet(
            label_style(12, color=Colors.ERROR, weight=600, font_family=Fonts.MONOSPACE)
            + "background: rgba(255, 59, 48, 0.1);border:none;border-radius:4px;padding:4px 8px;",
        )
        timer_label.setVisible(False)  # Hidden until recording starts
        nav_layout.addWidget(timer_label)

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
            "QFrame {  background: rgba(0, 0, 0, 0.04);  border-radius: 6px;}",
        )
        # Hide recording indicator box (keep for internal use but don't display)
        self.main_window.recording_indicator.setVisible(False)

        nav_layout.addSpacing(8)

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
            "  border-radius: 8px;"
            "}",
        )
        # Don't add to nav_layout - will be positioned as overlay in show_connecting_indicator

        nav_layout.addSpacing(16)  # Space between power button and logo

        # Company logo
        self._create_company_logo(nav_layout)

        return nav_widget

    def _create_pause_button(self, layout):
        """Create pause button with custom drawn lines."""
        self.main_window.pause_btn = QPushButton()
        self.main_window.pause_btn.setCheckable(True)
        self.main_window.pause_btn.setFixedSize(40, 40)
        self.main_window.pause_btn.setEnabled(
            False,
        )  # Disabled until acquisition starts
        self.main_window.pause_btn.setToolTip(
            "Pause Live Acquisition\n(Enabled after calibration)",
        )
        self.main_window.pause_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F5F5F7);"
            "  border: 1px solid rgba(46, 48, 227, 0.3);"
            "  border-radius: 8px;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(46, 48, 227, 0.1), stop:1 rgba(46, 48, 227, 0.15));"
            "  border: 1px solid rgba(46, 48, 227, 0.4);"
            "}"
            "QPushButton:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF9500, stop:1 #E68500);"
            "  border: 1px solid rgba(255, 149, 0, 0.3);"
            "}"
            "QPushButton:hover:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E68500, stop:1 #CC7700);"
            "  border: 1px solid rgba(230, 133, 0, 0.3);"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(46, 48, 227, 0.1);"
            "  border: 1px solid rgba(46, 48, 227, 0.1);"
            "}",
        )

        # Override paintEvent to draw custom pause lines
        def paint_pause_lines(event):
            """Draw two vertical lines for pause button."""
            # Call default painting first
            QPushButton.paintEvent(self.main_window.pause_btn, event)

            painter = QPainter(self.main_window.pause_btn)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Determine color based on state
            if not self.main_window.pause_btn.isEnabled():
                color = QColor(46, 48, 227, 77)  # 30% opacity
            elif self.main_window.pause_btn.isChecked():
                color = QColor(255, 255, 255)  # White when checked
            else:
                color = QColor(46, 48, 227)  # Blue when unchecked

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)

            # Draw two vertical rectangles (pause lines)
            line_width = 3
            line_height = 14
            gap = 4
            center_x = self.main_window.pause_btn.width() // 2
            center_y = self.main_window.pause_btn.height() // 2

            # Left line
            left_x = center_x - line_width - gap // 2
            painter.drawRoundedRect(
                left_x,
                center_y - line_height // 2,
                line_width,
                line_height,
                1.5,
                1.5,
            )

            # Right line
            right_x = center_x + gap // 2
            painter.drawRoundedRect(
                right_x,
                center_y - line_height // 2,
                line_width,
                line_height,
                1.5,
                1.5,
            )

            painter.end()

        self.main_window.pause_btn.paintEvent = paint_pause_lines
        self.main_window.pause_btn.clicked.connect(self.main_window._toggle_pause)
        layout.addWidget(self.main_window.pause_btn)

    def _create_record_button(self, layout):
        """Create record button."""
        self.main_window.record_btn = QPushButton("●")
        self.main_window.record_btn.setCheckable(True)
        self.main_window.record_btn.setFixedSize(40, 40)
        self.main_window.record_btn.setEnabled(
            False,
        )  # Disabled until acquisition starts
        self.main_window.record_btn.setToolTip(
            "Start Recording\n(Enabled after calibration)",
        )
        self.main_window.record_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F5F5F7);"
            "  color: rgb(46, 48, 227);"
            "  border: 1px solid rgba(46, 48, 227, 0.3);"
            "  border-radius: 8px;"
            "  font-size: 20px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(46, 48, 227, 0.1), stop:1 rgba(46, 48, 227, 0.15));"
            "  border: 1px solid rgba(46, 48, 227, 0.4);"
            "}"
            "QPushButton:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF3B30, stop:1 #E6342A);"
            "  color: white;"
            "  border: 1px solid rgba(255, 59, 48, 0.3);"
            "}"
            "QPushButton:hover:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E6342A, stop:1 #D02E24);"
            "  border: 1px solid rgba(230, 52, 42, 0.3);"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(46, 48, 227, 0.1);"
            "  color: rgba(46, 48, 227, 0.3);"
            "  border: 1px solid rgba(46, 48, 227, 0.1);"
            "}",
        )
        self.main_window.record_btn.clicked.connect(self.main_window._toggle_recording)
        layout.addWidget(self.main_window.record_btn)

    def _create_power_button(self, layout):
        """Create power button with state management."""
        self.main_window.power_btn = QPushButton("⏻")
        self.main_window.power_btn.setFixedSize(40, 40)
        self.main_window.power_btn.setProperty("powerState", "disconnected")

        # Apply original stylesheet with state-based coloring
        self.main_window.power_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(46, 48, 227, 0.4), stop:1 rgba(46, 48, 227, 0.5));"
            "  color: white;"
            "  border: 1px solid rgba(46, 48, 227, 0.2);"
            "  border-radius: 8px;"
            "  font-size: 20px;"
            "  font-weight: 400;"
            "  font-family: 'Segoe UI Symbol', 'Segoe UI Emoji', 'Apple Color Emoji', 'Arial Unicode MS', sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(46, 48, 227, 0.5), stop:1 rgba(46, 48, 227, 0.6));"
            "  border: 1px solid rgba(46, 48, 227, 0.3);"
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
        # Load logo using relative path from affilabs module
        logo_path = (
            Path(__file__).parent.parent / "ui" / "img" / "affinite-no-background.png"
        )

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

    def get_buttons(self) -> list[QPushButton]:
        """Get the list of navigation buttons.

        Returns:
            List of navigation QPushButton instances

        """
        return self.nav_buttons
