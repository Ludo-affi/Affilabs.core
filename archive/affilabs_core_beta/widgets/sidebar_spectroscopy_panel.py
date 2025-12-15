from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from widgets.spectroscopy import SpecPlot


class SidebarSpectroscopyPanel(QWidget):
    """Compact spectroscopy preview with graphs plus servo/LED controls."""

    polarizer_sig = Signal(str)
    single_led_sig = Signal(str)
    full_cal_sig = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.led_mode = "auto"
        self._last_single_channel = "a"
        self._syncing = False
        self.trans_toggle: QRadioButton | None = None
        self.raw_toggle: QRadioButton | None = None
        self.servo_combo: QComboBox | None = None
        self.led_mode_combo: QComboBox | None = None
        self.single_led_group: QGroupBox | None = None
        self.led_buttons: dict[str, QRadioButton] = {}
        self.led_button_group: QButtonGroup | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Transmission preview (top, always visible)
        self.trans_plot_view = SpecPlot("", "λ (nm)", "T (%)")
        self.trans_plot_view.setMinimumHeight(150)
        self.trans_plot_view.setMaximumHeight(200)

        # Intensity preview (raw data, hidden until toggle)
        self.intensity_plot_view = SpecPlot("", "λ (nm)", "I (counts)")
        self.intensity_plot_view.setMinimumHeight(150)
        self.intensity_plot_view.setMaximumHeight(200)

        for plot_widget in (self.trans_plot_view, self.intensity_plot_view):
            plot_widget.plot.showGrid(x=False, y=False)
            for axis_name in ("left", "bottom"):
                axis = plot_widget.plot.getAxis(axis_name)
                axis.setStyle(
                    tickLength=4,
                    maxTickLevel=0,
                    tickTextOffset=2,
                    showValues=True,
                )
            # Move x-axis label up by 10px
            bottom_axis = plot_widget.plot.getAxis("bottom")
            if bottom_axis.label is not None and hasattr(bottom_axis.label, "setPos"):
                orig_pos = bottom_axis.label.pos()
                bottom_axis.label.setPos(orig_pos.x(), orig_pos.y() - 10)
            if bottom_axis.label is not None and hasattr(
                bottom_axis.label,
                "setPadding",
            ):
                bottom_axis.label.setPadding(0)
            left_axis = plot_widget.plot.getAxis("left")
            if left_axis.label is not None and hasattr(left_axis.label, "setPadding"):
                left_axis.label.setPadding(0)
            self._shrink_plot_fonts(plot_widget)

        # Build toggle bar first (needed before wrapping)
        self.toggle_bar = self._build_graph_toggle_bar()

        # Wrap sections - transmission gets title and toggles
        self.trans_section = self._wrap_plot_section(
            self.trans_plot_view,
            add_title=True,
            add_toggles=True,
        )
        self.intensity_section = self._wrap_plot_section(self.intensity_plot_view)

        layout.addWidget(self.trans_section)
        layout.addWidget(self.intensity_section)
        self.intensity_section.setVisible(False)
        self.intensity_section.setFixedHeight(0)

        # Servo/LED controls in styled container
        layout.addWidget(self._build_controls_container())

        # Full Calibration button
        self.full_calibrate_btn = QPushButton("Full Calibration", self)
        self.full_calibrate_btn.setObjectName("full_calibrate_btn")
        self.full_calibrate_btn.setMinimumHeight(35)
        self.full_calibrate_btn.setMaximumHeight(40)
        self.full_calibrate_btn.clicked.connect(lambda: self.full_cal_sig.emit())
        layout.addWidget(self.full_calibrate_btn)

        # Advanced settings (hidden by default to save space)
        self.advanced = QGroupBox("Advanced Settings", self)
        self.advanced.setObjectName("advanced")
        self.advanced.setVisible(False)  # Hide by default to prevent overlap
        adv_layout = QVBoxLayout(self.advanced)
        adv_layout.setContentsMargins(4, 8, 4, 8)
        adv_layout.setSpacing(6)
        layout.addWidget(self.advanced)

        layout.addStretch(1)
        self._update_graph_visibility()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_graph_aspect()

    def _shrink_plot_fonts(self, plot_widget: SpecPlot) -> None:
        small_font = QFont("Segoe UI", 7)
        for axis_name in ("left", "bottom"):
            axis = plot_widget.plot.getAxis(axis_name)
            axis.setTickFont(small_font)
            if axis.label is not None:
                axis.label.setFont(small_font)

    def _wrap_plot_section(
        self,
        plot_widget: SpecPlot,
        add_title: bool = False,
        add_toggles: bool = False,
    ) -> QFrame:
        from ui.styles import Colors, Typography, get_container_style

        container = QFrame(self)
        container.setObjectName("spec_preview")
        container.setStyleSheet(get_container_style(elevated=True))
        container.setFrameShape(QFrame.StyledPanel)
        container.setFrameShadow(QFrame.Raised)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Add title if requested
        if add_title:
            from ui.styles import Colors, Typography

            title = QLabel("Spectroscopy", container)
            title.setStyleSheet(
                f"font-weight: 600; font-size: {Typography.SIZE_TITLE}pt; color: {Colors.ON_SURFACE}; background: transparent; border: none;",
            )
            title.setAlignment(Qt.AlignLeft)
            layout.addWidget(title)

        # Wrap plot in a frame with dark grey border
        from ui.styles import get_graph_border_style

        plot_frame = QFrame(container)
        plot_frame.setStyleSheet(get_graph_border_style())
        plot_layout = QVBoxLayout(plot_frame)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.addWidget(plot_widget)
        layout.addWidget(plot_frame)

        # Add toggle buttons if requested
        if add_toggles:
            layout.addWidget(self._build_graph_toggle_bar())

        return container

    def _build_graph_toggle_bar(self) -> QFrame:
        bar = QFrame(self)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 6, 4, 0)
        layout.setSpacing(6)

        dot_style = (
            "QRadioButton::indicator {"
            " width: 7px;"
            " height: 7px;"
            " border-radius: 3px;"
            " border: 2px solid rgb(150, 150, 150);"
            " background: transparent;"
            "}"
            "QRadioButton::indicator:checked {"
            " background: rgb(0, 102, 204);"
            " border-color: rgb(0, 102, 204);"
            "}"
        )

        self.trans_toggle = QRadioButton(bar)
        self.trans_toggle.setStyleSheet(dot_style)
        self.trans_toggle.setChecked(True)
        self.trans_toggle.setToolTip("Show transmission preview")

        self.raw_toggle = QRadioButton(bar)
        self.raw_toggle.setStyleSheet(dot_style)
        self.raw_toggle.setToolTip("Show raw intensity preview")

        layout.addStretch(1)
        layout.addWidget(self.trans_toggle)
        layout.addSpacing(4)
        layout.addWidget(self.raw_toggle)
        layout.addStretch(1)

        self.trans_toggle.toggled.connect(self._update_graph_visibility)
        self.raw_toggle.toggled.connect(self._update_graph_visibility)

        return bar

    def _build_controls_container(self) -> QFrame:
        """Build styled container for Pol and LED controls."""
        from ui.styles import Colors, Typography, get_container_style

        container = QFrame(self)
        container.setObjectName("pol_led_container")
        container.setStyleSheet(get_container_style(elevated=True))
        container.setFrameShape(QFrame.StyledPanel)
        container.setFrameShadow(QFrame.Raised)
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(8)

        # Add title
        title = QLabel("Pol and LED Control", container)
        title.setStyleSheet(
            f"font-weight: 600; font-size: {Typography.SIZE_TITLE}pt; color: {Colors.ON_SURFACE}; background: transparent; border: none;",
        )
        title.setAlignment(Qt.AlignLeft)
        outer_layout.addWidget(title)

        # Inner box for controls
        box = QGroupBox(container)
        box.setFlat(True)
        box.setStyleSheet("QGroupBox { border: none; background: transparent; }")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        # Servo (polarizer) control
        servo_row = QHBoxLayout()
        servo_row.setSpacing(8)
        servo_label = QLabel("Polarization Servo:", box)
        self.servo_combo = QComboBox(box)
        self.servo_combo.setStyleSheet(
            "QComboBox, QComboBox QAbstractItemView { color: black; background: white; }",
        )
        self.servo_combo.addItems(["P", "S"])
        self.servo_combo.currentTextChanged.connect(self._handle_servo_change)
        servo_row.addWidget(servo_label)
        servo_row.addStretch(1)
        servo_row.addWidget(self.servo_combo)
        layout.addLayout(servo_row)

        # LED mode selection
        led_grid = QGridLayout()
        led_grid.setHorizontalSpacing(8)
        led_grid.setVerticalSpacing(6)
        led_mode_label = QLabel("LED Mode:", box)
        self.led_mode_combo = QComboBox(box)
        self.led_mode_combo.setStyleSheet(
            "QComboBox, QComboBox QAbstractItemView { color: black; background: white; }",
        )
        self.led_mode_combo.addItems(["Auto", "Single"])
        self.led_mode_combo.currentTextChanged.connect(self._handle_led_mode_change)
        led_grid.addWidget(led_mode_label, 0, 0)
        led_grid.addWidget(self.led_mode_combo, 0, 1, 1, 2)

        led_select_label = QLabel("LED On:", box)
        led_grid.addWidget(led_select_label, 1, 0, Qt.AlignTop)

        # LED radio buttons (no separate channel labels)
        self.single_led_group = QGroupBox(box)
        self.single_led_group.setFlat(True)
        self.single_led_group.setStyleSheet(
            "QGroupBox { border: none; background: transparent; }",
        )
        single_layout = QHBoxLayout(self.single_led_group)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.setSpacing(8)
        self.led_buttons = {}
        self.led_button_group = QButtonGroup(self)
        for ch in ["Off", "A", "B", "C", "D"]:
            button = QRadioButton(ch, self.single_led_group)
            button.setStyleSheet(
                "QRadioButton { padding: 2px; }"
                "QRadioButton::indicator { width: 14px; height: 14px; margin-right: 4px; }",
            )
            self.led_button_group.addButton(button)
            single_layout.addWidget(button)
            normalized = ch.lower() if ch != "Off" else "x"
            self.led_buttons[normalized] = button
            button.toggled.connect(partial(self._handle_single_led_select, normalized))
        single_layout.addStretch(1)
        self.led_buttons["x"].setChecked(True)
        self.single_led_group.setEnabled(False)
        led_grid.addWidget(self.single_led_group, 1, 1, 1, 2, Qt.AlignLeft)
        layout.addLayout(led_grid)

        outer_layout.addWidget(box)
        return container

    def _handle_led_mode_change(self, mode_text: str) -> None:
        mode_lower = mode_text.strip().lower()
        if mode_lower == "auto":
            self.single_led_group.setEnabled(False)
            self.led_mode = "auto"
            if not self._syncing:
                self.single_led_sig.emit(self.led_mode)
        else:
            self.single_led_group.setEnabled(True)
            # Restore last selection when re-entering single mode
            target = self._last_single_channel
            if target not in self.led_buttons:
                target = "a"
            self.led_buttons[target].setChecked(True)
            self.led_mode = target
            if not self._syncing:
                self.single_led_sig.emit(self.led_mode)

    def _handle_single_led_select(self, channel: str, checked: bool) -> None:
        if not checked or not self.single_led_group.isEnabled():
            return
        self.led_mode = channel
        if channel != "x":
            self._last_single_channel = channel
        if not self._syncing:
            self.single_led_sig.emit(self.led_mode)

    def _handle_servo_change(self, text: str) -> None:
        if self._syncing:
            return
        self.polarizer_sig.emit(text.strip().lower())

    def update_data(self, spec_data: dict[str, object] | None) -> None:
        if not spec_data:
            return
        try:
            self.intensity_plot_view.update_plots(
                spec_data["wave_data"],
                spec_data["int_data"],
                self.led_mode,
            )
            self.trans_plot_view.update_plots(
                spec_data["wave_data"],
                spec_data["trans_data"],
                self.led_mode,
            )
        except Exception:
            # Keep sidebar resilient – plotting errors should not break UI
            pass

    def enable_controls(self, state: bool) -> None:
        self.servo_combo.setEnabled(state)
        self.led_mode_combo.setEnabled(state)
        self.single_led_group.setEnabled(
            state and self.led_mode_combo.currentText().lower() == "single",
        )

    def sync_polarizer(self, mode: str) -> None:
        normalized = (mode or "").strip().upper()
        if normalized not in {"P", "S"}:
            return
        if self.servo_combo.currentText() == normalized:
            return
        self._syncing = True
        self.servo_combo.setCurrentText(normalized)
        self._syncing = False

    def sync_led_mode(self, mode: str) -> None:
        normalized = (mode or "auto").strip().lower()
        target_combo = "Auto" if normalized == "auto" else "Single"
        self._syncing = True
        self.led_mode_combo.setCurrentText(target_combo)
        if normalized == "auto":
            self.led_buttons["x"].setChecked(True)
        else:
            target = normalized if normalized in self.led_buttons else "x"
            self.led_buttons[target].setChecked(True)
        self._syncing = False
        self.led_mode = normalized
        if normalized not in {"auto", "x"}:
            self._last_single_channel = normalized

    def _update_graph_visibility(self) -> None:
        trans_selected = (
            self.trans_toggle.isChecked() if hasattr(self, "trans_toggle") else True
        )
        raw_selected = (
            self.raw_toggle.isChecked() if hasattr(self, "raw_toggle") else False
        )

        # Show/hide only the section, don't set fixed height to 0
        # This preserves the title and toggle buttons
        self.trans_section.setVisible(trans_selected)
        self.intensity_section.setVisible(raw_selected)

        # Don't set fixed height - let the layout manage it naturally
        # The toggle bar and title remain visible

        self._update_graph_aspect()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_graph_aspect()

    def _update_graph_aspect(self) -> None:
        # Let the layout naturally manage heights
        # The visible graph section will size based on its content
        pass

    @property
    def _graph_frames(self):
        frames = []
        if hasattr(self, "trans_section"):
            frames.append(self.trans_section)
        if hasattr(self, "intensity_section"):
            frames.append(self.intensity_section)
        return frames
