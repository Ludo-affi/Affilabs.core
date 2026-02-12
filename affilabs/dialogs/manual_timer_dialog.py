"""Manual Timer Dialog - Set custom countdown timers for experiments.

This dialog allows users to manually set a countdown timer for tracking
experiment phases, wait times, or other time-based operations that aren't
part of the automated cycle queue.

FEATURES:
- Preset times (5 min, 15 min, custom)
- Save custom presets
- Font size toggle (normal/large)
- Sound notification on completion

USAGE:
    from affilabs.dialogs.manual_timer_dialog import ManualTimerDialog

    dialog = ManualTimerDialog(parent=main_window)
    if dialog.exec() == ManualTimerDialog.DialogCode.Accepted:
        minutes, seconds = dialog.get_duration()
        label = dialog.get_label()
        font_size = dialog.get_font_size()
        sound_enabled = dialog.get_sound_enabled()
        # Start custom timer with settings
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from affilabs.ui_styles import Colors, Fonts

class ManualTimerDialog(QDialog):
    """Modal dialog for setting manual countdown timers.

    Allows user to specify:
    - Timer duration (minutes and seconds)
    - Optional label/description
    - Font size (normal/large)
    - Sound notification
    - Preset times and custom presets
    """

    # Default presets (minutes)
    DEFAULT_PRESETS = [
        {"name": "5 min", "minutes": 5, "seconds": 0},
        {"name": "15 min", "minutes": 15, "seconds": 0},
        {"name": "30 min", "minutes": 30, "seconds": 0},
    ]

    def __init__(self, parent=None):
        """Initialize manual timer dialog.

        Args:
            parent: Parent widget for positioning
        """
        super().__init__(parent)

        self.setWindowTitle("Set Manual Timer")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setMinimumHeight(400)

        # Remove close button (force user to click Set or Cancel)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        # Load custom presets from settings
        self.custom_presets = self._load_custom_presets()

        self._setup_ui()

    def _setup_ui(self):
        """Build dialog UI with clean, modern design."""
        # Main container
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Set dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background: #FFFFFF;

            }}
        """)

        # Header section
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: #007AFF;
            }
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(6)

        title = QLabel("⏱ Set Manual Timer")
        title.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 600;
            color: white;
            font-family: {Fonts.SYSTEM};
        """)
        header_layout.addWidget(title)

        subtitle = QLabel("Set a custom countdown timer for your experiment")
        subtitle.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 400;
            color: rgba(255, 255, 255, 0.9);
            font-family: {Fonts.SYSTEM};
        """)
        header_layout.addWidget(subtitle)

        main_layout.addWidget(header)

        # Content section
        content = QFrame()
        content.setStyleSheet("""
            QFrame {
                background: #F8F9FA;
            }
        """)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)

        # Timer duration inputs
        duration_card = QFrame()
        duration_card.setStyleSheet("""
            QFrame {
                background: white;

            }
        """)
        duration_layout = QVBoxLayout(duration_card)
        duration_layout.setContentsMargins(16, 16, 16, 16)
        duration_layout.setSpacing(12)

        # Duration label
        duration_label = QLabel("Duration")
        duration_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            color: {Colors.PRIMARY_TEXT};
            font-family: {Fonts.SYSTEM};
        """)
        duration_layout.addWidget(duration_label)

        # Minutes and seconds inputs
        time_input_layout = QHBoxLayout()
        time_input_layout.setSpacing(12)

        # Minutes
        minutes_container = QVBoxLayout()
        minutes_container.setSpacing(4)

        minutes_label = QLabel("Minutes")
        minutes_label.setStyleSheet(f"""
            font-size: 12px;
            color: {Colors.SECONDARY_TEXT};
            font-family: {Fonts.SYSTEM};
        """)
        minutes_container.addWidget(minutes_label)

        self.minutes_input = QSpinBox()
        self.minutes_input.setRange(0, 999)
        self.minutes_input.setValue(5)
        self.minutes_input.setFixedHeight(36)
        self.minutes_input.setStyleSheet(f"""
            QSpinBox {{
                background: #F8F9FA;

                padding: 6px 12px;
                font-size: 14px;
                color: {Colors.PRIMARY_TEXT};
                font-family: {Fonts.SYSTEM};
            }}
            QSpinBox:focus {{

                background: white;
            }}
        """)
        minutes_container.addWidget(self.minutes_input)
        time_input_layout.addLayout(minutes_container)

        # Seconds
        seconds_container = QVBoxLayout()
        seconds_container.setSpacing(4)

        seconds_label = QLabel("Seconds")
        seconds_label.setStyleSheet(f"""
            font-size: 12px;
            color: {Colors.SECONDARY_TEXT};
            font-family: {Fonts.SYSTEM};
        """)
        seconds_container.addWidget(seconds_label)

        self.seconds_input = QSpinBox()
        self.seconds_input.setRange(0, 59)
        self.seconds_input.setValue(0)
        self.seconds_input.setFixedHeight(36)
        self.seconds_input.setStyleSheet(f"""
            QSpinBox {{
                background: #F8F9FA;

                padding: 6px 12px;
                font-size: 14px;
                color: {Colors.PRIMARY_TEXT};
                font-family: {Fonts.SYSTEM};
            }}
            QSpinBox:focus {{

                background: white;
            }}
        """)
        seconds_container.addWidget(self.seconds_input)
        time_input_layout.addLayout(seconds_container)

        duration_layout.addLayout(time_input_layout)

        # Preset buttons
        presets_row = QHBoxLayout()
        presets_row.setSpacing(8)

        preset_label = QLabel("Quick:")
        preset_label.setStyleSheet(f"""
            font-size: 12px;
            color: {Colors.SECONDARY_TEXT};
            font-family: {Fonts.SYSTEM};
        """)
        presets_row.addWidget(preset_label)

        # Add default preset buttons
        for preset in self.DEFAULT_PRESETS:
            btn = QPushButton(preset["name"])
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton {
                    background: #E8E8EA;

                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: 500;
                    color: #1D1D1F;
                }
                QPushButton:hover {
                    background: #D1D1D6;
                }
                QPushButton:pressed {
                    background: #C7C7CC;
                }
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, p=preset: self._apply_preset(p))
            presets_row.addWidget(btn)

        # Add custom preset buttons
        for preset in self.custom_presets:
            btn = QPushButton(preset["name"])
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton {
                    background: #007AFF;

                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: 500;
                    color: white;
                }
                QPushButton:hover {
                    background: #0051D5;
                }
                QPushButton:pressed {
                    background: #003D99;
                }
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, p=preset: self._apply_preset(p))
            presets_row.addWidget(btn)

        presets_row.addStretch()

        # Save preset button
        save_preset_btn = QPushButton("+ Save")
        save_preset_btn.setFixedHeight(28)
        save_preset_btn.setStyleSheet("""
            QPushButton {
                background: #34C759;

                padding: 4px 12px;
                font-size: 12px;
                font-weight: 500;
                color: white;
            }
            QPushButton:hover {
                background: #2FB350;
            }
            QPushButton:pressed {
                background: #28A745;
            }
        """)
        save_preset_btn.setToolTip("Save current time as custom preset")
        save_preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_preset_btn.clicked.connect(self._save_custom_preset)
        presets_row.addWidget(save_preset_btn)

        duration_layout.addLayout(presets_row)

        content_layout.addWidget(duration_card)

        # Timer options (font size and sound)
        options_card = QFrame()
        options_card.setStyleSheet("""
            QFrame {
                background: white;

            }
        """)
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(16, 16, 16, 16)
        options_layout.setSpacing(12)

        # Options label
        options_label = QLabel("Timer Options")
        options_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            color: {Colors.PRIMARY_TEXT};
            font-family: {Fonts.SYSTEM};
        """)
        options_layout.addWidget(options_label)

        # Font size selection
        font_size_row = QHBoxLayout()
        font_size_row.setSpacing(12)

        font_size_label = QLabel("Font Size:")
        font_size_label.setStyleSheet(f"""
            font-size: 13px;
            color: {Colors.PRIMARY_TEXT};
            font-family: {Fonts.SYSTEM};
        """)
        font_size_row.addWidget(font_size_label)

        # Font size buttons (toggle group)
        self.font_normal_btn = QPushButton("Normal")
        self.font_normal_btn.setCheckable(True)
        self.font_normal_btn.setChecked(True)
        self.font_normal_btn.setFixedHeight(32)
        self.font_normal_btn.clicked.connect(lambda: self._set_font_size("normal"))

        self.font_large_btn = QPushButton("Large")
        self.font_large_btn.setCheckable(True)
        self.font_large_btn.setChecked(False)
        self.font_large_btn.setFixedHeight(32)
        self.font_large_btn.clicked.connect(lambda: self._set_font_size("large"))

        font_btn_style = """
            QPushButton {
                background: #E8E8EA;

                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
                color: #1D1D1F;
            }
            QPushButton:hover {
                background: #D1D1D6;
            }
            QPushButton:checked {
                background: #007AFF;
                color: white;
            }
        """
        self.font_normal_btn.setStyleSheet(font_btn_style)
        self.font_large_btn.setStyleSheet(font_btn_style)
        self.font_normal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.font_large_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        font_size_row.addWidget(self.font_normal_btn)
        font_size_row.addWidget(self.font_large_btn)
        font_size_row.addStretch()

        options_layout.addLayout(font_size_row)

        # Sound notification checkbox
        self.sound_checkbox = QCheckBox("🔔 Play sound when timer completes")
        self.sound_checkbox.setChecked(True)
        self.sound_checkbox.setStyleSheet(f"""
            QCheckBox {{
                font-size: 13px;
                color: {Colors.PRIMARY_TEXT};
                font-family: {Fonts.SYSTEM};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;

                background: white;
            }}
            QCheckBox::indicator:checked {{
                background: #007AFF;
                border-color: #007AFF;
            }}
        """)
        options_layout.addWidget(self.sound_checkbox)

        content_layout.addWidget(options_card)

        # Label input (optional)
        label_card = QFrame()
        label_card.setStyleSheet("""
            QFrame {
                background: white;

            }
        """)
        label_layout = QVBoxLayout(label_card)
        label_layout.setContentsMargins(16, 16, 16, 16)
        label_layout.setSpacing(8)

        label_label = QLabel("Label (Optional)")
        label_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            color: {Colors.PRIMARY_TEXT};
            font-family: {Fonts.SYSTEM};
        """)
        label_layout.addWidget(label_label)

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("e.g., Incubation, Wait time, etc.")
        self.label_input.setFixedHeight(36)
        self.label_input.setStyleSheet(f"""
            QLineEdit {{
                background: #F8F9FA;

                padding: 6px 12px;
                font-size: 14px;
                color: {Colors.PRIMARY_TEXT};
                font-family: {Fonts.SYSTEM};
            }}
            QLineEdit:focus {{

                background: white;
            }}
        """)
        label_layout.addWidget(self.label_input)

        content_layout.addWidget(label_card)

        # Button row
        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.setContentsMargins(0, 8, 0, 0)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F7;

                padding: 0px 24px;
                font-size: 14px;
                font-weight: 500;
                color: #1D1D1F;
            }
            QPushButton:hover {
                background: #E5E5EA;
                border-color: #C7C7CC;
            }
            QPushButton:pressed {
                background: #D1D1D6;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(cancel_btn)

        button_row.addStretch()

        # Set Timer button
        set_btn = QPushButton("⏱ Set Timer")
        set_btn.setFixedHeight(38)
        set_btn.setStyleSheet("""
            QPushButton {
                background: #007AFF;

                padding: 0px 32px;
                font-size: 14px;
                font-weight: 600;
                color: white;
            }
            QPushButton:hover {
                background: #0051D5;
            }
            QPushButton:pressed {
                background: #003D99;
            }
        """)
        set_btn.clicked.connect(self.accept)
        set_btn.setDefault(True)
        set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(set_btn)

        content_layout.addLayout(button_row)

        main_layout.addWidget(content)

    def get_duration(self) -> Tuple[int, int]:
        """Get the timer duration selected by user.

        Returns:
            Tuple of (minutes, seconds)
        """
        return (self.minutes_input.value(), self.seconds_input.value())

    def get_label(self) -> Optional[str]:
        """Get the optional label text.

        Returns:
            Label text if provided, None otherwise
        """
        label = self.label_input.text().strip()
        return label if label else None

    def get_font_size(self) -> str:
        """Get the selected font size.

        Returns:
            "normal" or "large"
        """
        return "large" if self.font_large_btn.isChecked() else "normal"

    def get_sound_enabled(self) -> bool:
        """Get whether sound notification is enabled.

        Returns:
            True if sound should play on completion
        """
        return self.sound_checkbox.isChecked()

    def _apply_preset(self, preset: dict):
        """Apply a preset time to the inputs.

        Args:
            preset: Dictionary with 'minutes' and 'seconds' keys
        """
        self.minutes_input.setValue(preset["minutes"])
        self.seconds_input.setValue(preset["seconds"])

    def _set_font_size(self, size: str):
        """Set font size toggle state.

        Args:
            size: "normal" or "large"
        """
        if size == "normal":
            self.font_normal_btn.setChecked(True)
            self.font_large_btn.setChecked(False)
        else:
            self.font_normal_btn.setChecked(False)
            self.font_large_btn.setChecked(True)

    def _save_custom_preset(self):
        """Save current timer duration as a custom preset."""
        from PySide6.QtWidgets import QInputDialog

        minutes = self.minutes_input.value()
        seconds = self.seconds_input.value()

        if minutes == 0 and seconds == 0:
            return

        # Ask user for preset name
        name, ok = QInputDialog.getText(
            self,
            "Save Preset",
            "Enter preset name:",
            text=f"{minutes}:{seconds:02d}"
        )

        if ok and name:
            # Add to custom presets
            preset = {
                "name": name.strip(),
                "minutes": minutes,
                "seconds": seconds
            }
            self.custom_presets.append(preset)
            self._save_custom_presets_to_file()

            # Recreate UI to show new preset button
            # For simplicity, just inform user to reopen dialog
            from affilabs.utils.logger import logger
            logger.info(f"✓ Preset '{name}' saved. Reopen dialog to see it.")

    def _load_custom_presets(self) -> list:
        """Load custom presets from settings file.

        Returns:
            List of preset dictionaries
        """
        try:
            presets_file = Path.home() / ".claude" / "timer_presets.json"
            if presets_file.exists():
                with open(presets_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_custom_presets_to_file(self):
        """Save custom presets to settings file."""
        try:
            presets_file = Path.home() / ".claude" / "timer_presets.json"
            presets_file.parent.mkdir(parents=True, exist_ok=True)
            with open(presets_file, 'w') as f:
                json.dump(self.custom_presets, f, indent=2)
        except Exception as e:
            from affilabs.utils.logger import logger
            logger.error(f"Failed to save timer presets: {e}")
