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
    primary_button_style,
    section_header_style,
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
        """Build export format selection dropdown (Excel, CSV, JSON)."""
        format_section = QLabel("EXPORT FORMAT")
        format_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(format_section)
        tab_layout.addSpacing(8)

        format_card = QFrame()
        format_card.setStyleSheet(card_style())
        format_card_layout = QVBoxLayout(format_card)
        format_card_layout.setContentsMargins(12, 10, 12, 10)
        format_card_layout.setSpacing(8)

        # Export target dropdown (optimize for specific software)
        target_row = QHBoxLayout()
        target_row.setSpacing(10)

        target_label = QLabel("Optimize For:")
        target_label.setFixedWidth(100)
        target_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        target_row.addWidget(target_label)

        self.sidebar.export_target_combo = QComboBox()
        self.sidebar.export_target_combo.addItems([
            "Custom (Manual settings)",
            "GraphPad Prism",
            "Origin (OriginLab)",
            "TraceDrawer (Ridgeview)",
            "General Analysis"
        ])
        self.sidebar.export_target_combo.setCurrentIndex(0)  # Custom default
        self.sidebar.export_target_combo.setStyleSheet(self._combo_style())
        self.sidebar.export_target_combo.currentIndexChanged.connect(self._on_export_target_changed)
        target_row.addWidget(self.sidebar.export_target_combo)
        target_row.addStretch()
        format_card_layout.addLayout(target_row)

        # Add helpful info label
        info_label = QLabel("💡 Automatically configures format settings for selected software")
        info_label.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT)
            + "font-style: italic; margin-top: 4px; margin-bottom: 8px;",
        )
        format_card_layout.addWidget(info_label)

        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: rgba(0, 0, 0, 0.06); max-height: 1px; margin: 8px 0px;")
        format_card_layout.addWidget(separator)

        # Format dropdown
        format_row = QHBoxLayout()
        format_row.setSpacing(10)

        format_label = QLabel("File Format:")
        format_label.setFixedWidth(100)
        format_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        format_row.addWidget(format_label)

        self.sidebar.format_combo = QComboBox()
        self.sidebar.format_combo.addItems([
            "Excel (.xlsx) - Multi-tab workbook",
            "CSV (.csv) - Single or multiple files",
            "JSON (.json) - Structured data"
        ])
        self.sidebar.format_combo.setCurrentIndex(0)  # Excel default
        self.sidebar.format_combo.setStyleSheet(self._combo_style())
        self.sidebar.format_combo.currentIndexChanged.connect(self._on_manual_format_change)
        format_row.addWidget(self.sidebar.format_combo)
        format_row.addStretch()
        format_card_layout.addLayout(format_row)

        tab_layout.addWidget(format_card)
        tab_layout.addSpacing(16)

    def _build_file_settings(self, tab_layout: QVBoxLayout):
        """Build file settings section (filename, destination, export button)."""
        file_section = QLabel("FILE SETTINGS & EXPORT")
        file_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(file_section)
        tab_layout.addSpacing(8)

        file_card = QFrame()
        file_card.setStyleSheet(card_style())
        file_card_layout = QVBoxLayout(file_card)
        file_card_layout.setContentsMargins(12, 10, 12, 10)
        file_card_layout.setSpacing(10)

        # File name
        filename_label = QLabel("File Name:")
        filename_label.setFixedWidth(100)
        filename_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        file_card_layout.addWidget(filename_label)

        self.sidebar.export_filename_input = QLineEdit()
        # Set default filename with timestamp
        from affilabs.utils.time_utils import filename_timestamp
        default_name = f"spr_data_{filename_timestamp()}"
        self.sidebar.export_filename_input.setText(default_name)
        self.sidebar.export_filename_input.setToolTip(
            "Base filename (extension will be added automatically based on format)",
        )
        self.sidebar.export_filename_input.setStyleSheet(self._lineedit_style())
        file_card_layout.addWidget(self.sidebar.export_filename_input)

        # Destination folder
        dest_label = QLabel("Destination:")
        dest_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        file_card_layout.addWidget(dest_label)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(8)

        self.sidebar.export_dest_input = QLineEdit()
        self.sidebar.export_dest_input.setPlaceholderText(
            "C:/Users/Documents/Experiments",
        )
        self.sidebar.export_dest_input.setToolTip(
            "Default export directory (can browse or type path)",
        )
        self.sidebar.export_dest_input.setStyleSheet(self._lineedit_style())
        dest_row.addWidget(self.sidebar.export_dest_input)

        self.sidebar.export_browse_btn = QPushButton("Browse...")
        self.sidebar.export_browse_btn.setFixedHeight(32)
        self.sidebar.export_browse_btn.setFixedWidth(90)
        self.sidebar.export_browse_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.SECONDARY_TEXT};"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}",
        )
        self.sidebar.export_browse_btn.clicked.connect(
            self.sidebar._browse_export_destination,
        )
        dest_row.addWidget(self.sidebar.export_browse_btn)
        file_card_layout.addLayout(dest_row)

        # Estimated file size
        self.sidebar.export_filesize_label = QLabel(
            "Estimated file size: Calculating...",
        )
        self.sidebar.export_filesize_label.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT)
            + "font-style: italic; margin-top: 4px;",
        )
        file_card_layout.addWidget(self.sidebar.export_filesize_label)

        # Export button (Excel - always available)
        self.sidebar.export_data_btn = QPushButton("📁 Export Data (Excel)")
        self.sidebar.export_data_btn.setFixedHeight(40)
        self.sidebar.export_data_btn.setStyleSheet(primary_button_style())
        # Note: Connected in affilabs_core_ui.py to _on_export_data
        file_card_layout.addWidget(self.sidebar.export_data_btn)

        # AnIML Export button (Pro/Enterprise feature)
        file_card_layout.addSpacing(8)
        self.sidebar.export_animl_btn = QPushButton("📋 Export AnIML (Pro)")
        self.sidebar.export_animl_btn.setFixedHeight(36)
        self.sidebar.export_animl_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {Colors.BUTTON_PRIMARY};"
            f"  color: white;"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  padding: 8px 16px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: #005BBB; }}"
            f"QPushButton:disabled {{"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"}}"
        )
        self.sidebar.export_animl_btn.setToolTip(
            "Export data in AnIML format for regulatory compliance\n"
            "(Requires Pro or Enterprise license)"
        )
        # Note: Will be connected in affilabs_core_ui.py to _on_export_animl
        file_card_layout.addWidget(self.sidebar.export_animl_btn)

        tab_layout.addWidget(file_card)
        tab_layout.addSpacing(16)

    def _radio_button_style(self) -> str:
        """Return consistent radio button stylesheet."""
        return (
            f"QRadioButton {{"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  background: transparent;"
            f"  spacing: 6px;"
            f"  font-weight: 500;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QRadioButton::indicator {{"
            f"  width: 18px;"
            f"  height: 18px;"
            f"  border: 1.5px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 9px;"
            f"  background: white;"
            f"}}"
            f"QRadioButton::indicator:hover {{"
            f"  border-color: {Colors.OVERLAY_LIGHT_30};"
            f"}}"
            f"QRadioButton::indicator:checked {{"
            f"  background: {Colors.BUTTON_PRIMARY};"
            f"  border-color: {Colors.BUTTON_PRIMARY};"
            f"}}"
        )

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
