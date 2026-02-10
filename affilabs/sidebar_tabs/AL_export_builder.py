"""Export Tab Builder

Handles building the Export tab UI with data export options, format selection, and file management.

Author: Affilabs
"""

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

# Import styles from central location
from affilabs.ui_styles import (
    Colors,
    Fonts,
    card_style,
    label_style,
    section_header_style,
)

_MONO_BTN = (
    f"QPushButton {{"
    f"  background: #1D1D1F;"
    f"  color: white;"
    f"  border: none;"
    f"  border-radius: 6px;"
    f"  padding: 8px 16px;"
    f"  font-size: 12px;"
    f"  font-weight: 600;"
    f"  font-family: {Fonts.SYSTEM};"
    f"}}"
    f"QPushButton:hover {{ background: #3A3A3C; }}"
    f"QPushButton:disabled {{"
    f"  background: {Colors.OVERLAY_LIGHT_10};"
    f"  color: {Colors.SECONDARY_TEXT};"
    f"}}"
)


class ExportTabBuilder:
    """Builder for constructing the Export tab UI with data export functionality."""

    def __init__(self, sidebar):
        """Initialize builder with reference to parent sidebar.

        Args:
            sidebar: Parent AffilabsSidebar instance to attach widgets to

        """
        self.sidebar = sidebar

    def build(self, tab_layout: QVBoxLayout):
        """Build the complete Export tab UI.

        Args:
            tab_layout: QVBoxLayout to add export tab widgets to

        """
        self._build_export_format(tab_layout)
        self._build_file_settings(tab_layout)

    def _build_export_format(self, tab_layout: QVBoxLayout):
        """Build export format selection dropdown."""
        format_card = QFrame()
        format_card.setStyleSheet(card_style())
        format_card_layout = QVBoxLayout(format_card)
        format_card_layout.setContentsMargins(12, 8, 12, 8)
        format_card_layout.setSpacing(6)

        # Target software preset
        target_row = QHBoxLayout()
        target_row.setSpacing(8)
        target_label = QLabel("Target:")
        target_label.setFixedWidth(70)
        target_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        target_row.addWidget(target_label)

        self.sidebar.export_target_combo = QComboBox()
        self.sidebar.export_target_combo.addItems([
            "Custom",
            "GraphPad Prism",
            "Origin",
            "TraceDrawer",
            "General Analysis"
        ])
        self.sidebar.export_target_combo.setCurrentIndex(0)
        self.sidebar.export_target_combo.setStyleSheet(self._combo_style())
        self.sidebar.export_target_combo.currentIndexChanged.connect(self._on_export_target_changed)
        target_row.addWidget(self.sidebar.export_target_combo)
        format_card_layout.addLayout(target_row)

        # File format
        format_row = QHBoxLayout()
        format_row.setSpacing(8)
        format_label = QLabel("Format:")
        format_label.setFixedWidth(70)
        format_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        format_row.addWidget(format_label)

        self.sidebar.format_combo = QComboBox()
        self.sidebar.format_combo.addItems([
            "Excel (.xlsx)",
            "CSV (.csv)",
            "JSON (.json)"
        ])
        self.sidebar.format_combo.setCurrentIndex(0)
        self.sidebar.format_combo.setStyleSheet(self._combo_style())
        self.sidebar.format_combo.currentIndexChanged.connect(self._on_manual_format_change)
        format_row.addWidget(self.sidebar.format_combo)
        format_card_layout.addLayout(format_row)

        tab_layout.addWidget(format_card)
        tab_layout.addSpacing(6)

    def _build_file_settings(self, tab_layout: QVBoxLayout):
        """Build file settings section (filename, destination, export button)."""
        file_card = QFrame()
        file_card.setStyleSheet(card_style())
        file_card_layout = QVBoxLayout(file_card)
        file_card_layout.setContentsMargins(12, 8, 12, 8)
        file_card_layout.setSpacing(6)

        # File name
        filename_label = QLabel("File Name:")
        filename_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        file_card_layout.addWidget(filename_label)

        self.sidebar.export_filename_input = QLineEdit()
        from affilabs.utils.time_utils import filename_timestamp
        self.sidebar.export_filename_input.setText(f"spr_data_{filename_timestamp()}")
        self.sidebar.export_filename_input.setToolTip(
            "Base filename (extension added automatically)",
        )
        self.sidebar.export_filename_input.setStyleSheet(self._lineedit_style())
        file_card_layout.addWidget(self.sidebar.export_filename_input)

        # Destination folder
        dest_label = QLabel("Destination:")
        dest_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        file_card_layout.addWidget(dest_label)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(6)

        self.sidebar.export_dest_input = QLineEdit()
        self.sidebar.export_dest_input.setPlaceholderText("C:/Users/Documents/Experiments")
        self.sidebar.export_dest_input.setStyleSheet(self._lineedit_style())
        dest_row.addWidget(self.sidebar.export_dest_input)

        self.sidebar.export_browse_btn = QPushButton("...")
        self.sidebar.export_browse_btn.setFixedHeight(30)
        self.sidebar.export_browse_btn.setFixedWidth(36)
        self.sidebar.export_browse_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 4px;"
            f"  font-size: 13px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
        )
        self.sidebar.export_browse_btn.clicked.connect(
            self.sidebar._browse_export_destination,
        )
        dest_row.addWidget(self.sidebar.export_browse_btn)
        file_card_layout.addLayout(dest_row)

        # Estimated file size
        self.sidebar.export_filesize_label = QLabel("Estimated size: --")
        self.sidebar.export_filesize_label.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic;",
        )
        file_card_layout.addWidget(self.sidebar.export_filesize_label)

        file_card_layout.addSpacing(4)

        # Export button - monochrome
        self.sidebar.export_data_btn = QPushButton("Export Data")
        self.sidebar.export_data_btn.setFixedHeight(36)
        self.sidebar.export_data_btn.setStyleSheet(_MONO_BTN)
        file_card_layout.addWidget(self.sidebar.export_data_btn)

        # AnIML Export button - monochrome
        file_card_layout.addSpacing(4)
        self.sidebar.export_animl_btn = QPushButton("Export AnIML")
        self.sidebar.export_animl_btn.setFixedHeight(36)
        self.sidebar.export_animl_btn.setStyleSheet(_MONO_BTN)
        self.sidebar.export_animl_btn.setToolTip("AnIML format for regulatory compliance")
        file_card_layout.addWidget(self.sidebar.export_animl_btn)

        tab_layout.addWidget(file_card)
        tab_layout.addSpacing(6)

    def _on_export_target_changed(self, index: int):
        """Handle export target selection - auto-configure format for selected software."""
        if not hasattr(self.sidebar, 'export_target_combo'):
            return

        target = self.sidebar.export_target_combo.currentText()

        self.sidebar.format_combo.blockSignals(True)

        if "Prism" in target:
            self.sidebar.format_combo.setCurrentIndex(1)  # CSV
        elif "Origin" in target:
            self.sidebar.format_combo.setCurrentIndex(0)  # Excel
        elif "TraceDrawer" in target:
            self.sidebar.format_combo.setCurrentIndex(1)  # CSV
        elif "General Analysis" in target:
            self.sidebar.format_combo.setCurrentIndex(0)  # Excel

        self.sidebar.format_combo.blockSignals(False)

    def _on_manual_format_change(self, index: int):
        """Handle manual format change - switch to Custom mode."""
        if hasattr(self.sidebar, 'export_target_combo'):
            self.sidebar.export_target_combo.blockSignals(True)
            self.sidebar.export_target_combo.setCurrentIndex(0)  # Custom
            self.sidebar.export_target_combo.blockSignals(False)

    def _combo_style(self) -> str:
        """Return consistent combo box stylesheet."""
        return (
            f"QComboBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 4px 8px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: white;"
            f"  selection-background-color: {Colors.OVERLAY_LIGHT_10};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"}}"
        )

    def _lineedit_style(self) -> str:
        """Return consistent line edit stylesheet."""
        return (
            f"QLineEdit {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 6px 8px;"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QLineEdit:focus {{ border: 2px solid {Colors.PRIMARY_TEXT}; }}"
        )
