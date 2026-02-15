"""Manual Timer Dialog - Set custom countdown timers for experiments.

This dialog allows users to manually set a countdown timer for tracking
experiment phases, wait times, or other time-based operations that aren't
part of the automated cycle queue.

FEATURES:
- Single MM:SS duration input
- Preset times (5 min, 15 min, custom)
- Save custom presets
- Sound notification with real alarm bell on completion

USAGE:
    from affilabs.dialogs.manual_timer_dialog import ManualTimerDialog

    dialog = ManualTimerDialog(parent=main_window)
    if dialog.exec() == ManualTimerDialog.DialogCode.Accepted:
        minutes, seconds = dialog.get_duration()
        label = dialog.get_label()
        sound_enabled = dialog.get_sound_enabled()
        # Start custom timer with settings
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from affilabs.ui_styles import Colors, Fonts


class ManualTimerDialog(QDialog):
    """Modal dialog for setting manual countdown timers.

    Allows user to specify:
    - Timer duration (single MM:SS field)
    - Optional label/description
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
        self.setMinimumWidth(380)
        self.setMaximumWidth(420)

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
        self.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
            }
        """)

        # Header section with flat blue background
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: #007AFF;
            }
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(4)

        title = QLabel("\u23f1 Set Manual Timer")
        title.setStyleSheet(f"""
            font-size: 24px;
            font-weight: 800;
            color: white;
            font-family: {Fonts.DISPLAY};
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(title)

        subtitle = QLabel("Set a custom countdown timer for your experiment")
        subtitle.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.95);
            font-family: {Fonts.SYSTEM};
        """)
        header_layout.addWidget(subtitle)

        main_layout.addWidget(header)

        # Content section
        content = QFrame()
        content.setStyleSheet("""
            QFrame {
                background: #F5F5F7;
            }
        """)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(12)

        # ── Duration card ──
        duration_card = QFrame()
        duration_card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 8px;
            }
        """)
        duration_layout = QVBoxLayout(duration_card)
        duration_layout.setContentsMargins(14, 12, 14, 12)
        duration_layout.setSpacing(10)

        # Duration label
        duration_label = QLabel("\u23f1 Duration")
        duration_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {Colors.PRIMARY_TEXT};
            font-family: {Fonts.DISPLAY};
            letter-spacing: 0.3px;
        """)
        duration_layout.addWidget(duration_label)

        # Single MM:SS input field
        time_row = QHBoxLayout()
        time_row.setSpacing(8)

        self.duration_input = QLineEdit()
        self.duration_input.setPlaceholderText("MM:SS")
        self.duration_input.setText("05:00")
        self.duration_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.duration_input.setFixedHeight(48)
        self.duration_input.setMaxLength(6)  # up to 999:59

        # Allow digits and colon
        rx = QRegularExpression(r"^\d{1,3}:\d{0,2}$")
        self.duration_input.setValidator(QRegularExpressionValidator(rx))

        self.duration_input.setStyleSheet(f"""
            QLineEdit {{
                background: #F8F9FA;
                border: 1px solid #E5E5EA;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 28px;
                font-weight: 700;
                color: {Colors.PRIMARY_TEXT};
                font-family: {Fonts.MONOSPACE};
                letter-spacing: 4px;
            }}
            QLineEdit:focus {{
                border: 2px solid #007AFF;
                background: white;
            }}
        """)
        time_row.addWidget(self.duration_input)
        duration_layout.addLayout(time_row)

        # Preset buttons row
        presets_row = QHBoxLayout()
        presets_row.setSpacing(8)

        preset_label = QLabel("Quick:")
        preset_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {Colors.PRIMARY_TEXT};
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
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 13px;
                    font-weight: 700;
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
                    border-radius: 6px;
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
                border-radius: 6px;
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

        # ── Timer Options card ──
        options_card = QFrame()
        options_card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 8px;
            }
        """)
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(16, 16, 16, 16)
        options_layout.setSpacing(12)

        options_label = QLabel("\u2699 Timer Options")
        options_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {Colors.PRIMARY_TEXT};
            font-family: {Fonts.DISPLAY};
            letter-spacing: 0.3px;
        """)
        options_layout.addWidget(options_label)

        checkbox_style = f"""
            QCheckBox {{
                font-size: 14px;
                font-weight: 600;
                color: {Colors.PRIMARY_TEXT};
                font-family: {Fonts.SYSTEM};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid #C7C7CC;
                border-radius: 4px;
                background: white;
            }}
            QCheckBox::indicator:hover {{
                border-color: #007AFF;
            }}
            QCheckBox::indicator:checked {{
                background: #007AFF;
                border-color: #007AFF;
            }}
        """

        # Sound notification checkbox
        self.sound_checkbox = QCheckBox("\U0001f514 Play alarm sound when timer completes")
        self.sound_checkbox.setChecked(True)
        self.sound_checkbox.setStyleSheet(checkbox_style)
        options_layout.addWidget(self.sound_checkbox)

        content_layout.addWidget(options_card)

        # ── Label card ──
        label_card = QFrame()
        label_card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 8px;
            }
        """)
        label_layout = QVBoxLayout(label_card)
        label_layout.setContentsMargins(14, 12, 14, 12)
        label_layout.setSpacing(6)

        label_label = QLabel("\U0001f3f7 Label (Optional)")
        label_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {Colors.PRIMARY_TEXT};
            font-family: {Fonts.DISPLAY};
            letter-spacing: 0.3px;
        """)
        label_layout.addWidget(label_label)

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("e.g., Incubation, Wait time, etc.")
        self.label_input.setFixedHeight(36)
        self.label_input.setStyleSheet(f"""
            QLineEdit {{
                background: #F8F9FA;
                border: 1px solid #E5E5EA;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 15px;
                font-weight: 600;
                color: {Colors.PRIMARY_TEXT};
                font-family: {Fonts.SYSTEM};
            }}
            QLineEdit:focus {{
                border: 1px solid #007AFF;
                background: white;
            }}
        """)
        label_layout.addWidget(self.label_input)

        content_layout.addWidget(label_card)

        # ── Button row ──
        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.setContentsMargins(0, 8, 0, 0)

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
            }
            QPushButton:pressed {
                background: #D1D1D6;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(cancel_btn)

        button_row.addStretch()

        set_btn = QPushButton("\u23f1 Set Timer")
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

    # ------------------------------------------------------------------
    #  Public getters
    # ------------------------------------------------------------------

    def get_duration(self) -> Tuple[int, int]:
        """Get the timer duration selected by user.

        Returns:
            Tuple of (minutes, seconds)
        """
        text = self.duration_input.text().strip()
        try:
            parts = text.split(":")
            minutes = int(parts[0]) if parts[0] else 0
            seconds = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            # Clamp seconds to 0-59 and carry over
            if seconds >= 60:
                minutes += seconds // 60
                seconds = seconds % 60
            return (minutes, seconds)
        except (ValueError, IndexError):
            return (0, 0)

    def get_label(self) -> Optional[str]:
        """Get the optional label text.

        Returns:
            Label text if provided, None otherwise
        """
        label = self.label_input.text().strip()
        return label if label else None

    def get_font_size(self) -> str:
        """Get the selected font size (always 'normal' - legacy compat).

        Returns:
            "normal"
        """
        return "normal"

    def get_sound_enabled(self) -> bool:
        """Get whether sound notification is enabled.

        Returns:
            True if sound should play on completion
        """
        return self.sound_checkbox.isChecked()

    def get_popout_enabled(self) -> bool:
        """Get whether the pop-out timer window should be shown.

        Returns:
            True if pop-out window should appear
        """
        return True  # Always enabled (option removed from UI)

    def get_rolling_numbers_enabled(self) -> bool:
        """Get whether rolling number animation should be enabled.

        Returns:
            True if rolling number animation should be used
        """
        return False  # Disabled (option removed from UI)

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _apply_preset(self, preset: dict):
        """Apply a preset time to the input field.

        Args:
            preset: Dictionary with 'minutes' and 'seconds' keys
        """
        m = preset["minutes"]
        s = preset.get("seconds", 0)
        self.duration_input.setText(f"{m:02d}:{s:02d}")

    def _save_custom_preset(self):
        """Save current timer duration as a custom preset."""
        from PySide6.QtWidgets import QInputDialog

        minutes, seconds = self.get_duration()

        if minutes == 0 and seconds == 0:
            return

        # Ask user for preset name
        name, ok = QInputDialog.getText(
            self,
            "Save Preset",
            "Enter preset name:",
            text=f"{minutes}:{seconds:02d}",
        )

        if ok and name:
            preset = {
                "name": name.strip(),
                "minutes": minutes,
                "seconds": seconds,
            }
            self.custom_presets.append(preset)
            self._save_custom_presets_to_file()

            from affilabs.utils.logger import logger

            logger.info(f"\u2713 Preset '{name}' saved. Reopen dialog to see it.")

    def _load_custom_presets(self) -> list:
        """Load custom presets from settings file.

        Returns:
            List of preset dictionaries
        """
        try:
            presets_file = Path.home() / ".claude" / "timer_presets.json"
            if presets_file.exists():
                with open(presets_file, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_custom_presets_to_file(self):
        """Save custom presets to settings file."""
        try:
            presets_file = Path.home() / ".claude" / "timer_presets.json"
            presets_file.parent.mkdir(parents=True, exist_ok=True)
            with open(presets_file, "w") as f:
                json.dump(self.custom_presets, f, indent=2)
        except Exception as e:
            from affilabs.utils.logger import logger

            logger.error(f"Failed to save timer presets: {e}")
