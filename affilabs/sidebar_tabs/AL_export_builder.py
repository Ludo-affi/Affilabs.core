"""Export Tab Builder

Handles building the Export tab UI with data export options, format selection, and file management.

Author: Affilabs
"""

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

# Import styles from central location
from affilabs.ui_styles import (
    Colors,
    Fonts,
    card_style,
    checkbox_style,
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
        self._build_data_selection(tab_layout)
        self._build_channel_selection(tab_layout)
        self._build_export_format(tab_layout)
        self._build_export_options(tab_layout)
        self._build_file_settings(tab_layout)
        self._build_quick_presets(tab_layout)

    def _build_data_selection(self, tab_layout: QVBoxLayout):
        """Build data selection section with checkboxes for different data types."""
        data_selection_section = QLabel("DATA SELECTION")
        data_selection_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(data_selection_section)
        tab_layout.addSpacing(8)

        data_selection_card = QFrame()
        data_selection_card.setStyleSheet(card_style())
        data_selection_card_layout = QVBoxLayout(data_selection_card)
        data_selection_card_layout.setContentsMargins(12, 10, 12, 10)
        data_selection_card_layout.setSpacing(8)

        # Data type checkboxes
        self.sidebar.raw_data_check = QCheckBox("Raw Sensorgram Data")
        self.sidebar.raw_data_check.setChecked(True)
        self.sidebar.raw_data_check.setStyleSheet(checkbox_style())
        self.sidebar.raw_data_check.setToolTip(
            "Export unprocessed sensorgram data (time-series wavelength shifts)",
        )
        data_selection_card_layout.addWidget(self.sidebar.raw_data_check)

        self.sidebar.processed_data_check = QCheckBox(
            "Processed Data (filtered/smoothed)",
        )
        self.sidebar.processed_data_check.setChecked(True)
        self.sidebar.processed_data_check.setStyleSheet(checkbox_style())
        self.sidebar.processed_data_check.setToolTip(
            "Export data with filtering and smoothing applied",
        )
        data_selection_card_layout.addWidget(self.sidebar.processed_data_check)

        self.sidebar.cycle_segments_check = QCheckBox("Cycle Segments (with metadata)")
        self.sidebar.cycle_segments_check.setChecked(True)
        self.sidebar.cycle_segments_check.setStyleSheet(checkbox_style())
        data_selection_card_layout.addWidget(self.sidebar.cycle_segments_check)

        self.sidebar.summary_table_check = QCheckBox("Summary Table")
        self.sidebar.summary_table_check.setChecked(True)
        self.sidebar.summary_table_check.setStyleSheet(checkbox_style())
        data_selection_card_layout.addWidget(self.sidebar.summary_table_check)

        tab_layout.addWidget(data_selection_card)
        tab_layout.addSpacing(16)

    def _build_channel_selection(self, tab_layout: QVBoxLayout):
        """Build channel selection section with checkboxes for A, B, C, D channels."""
        channel_section = QLabel("CHANNEL SELECTION")
        channel_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(channel_section)
        tab_layout.addSpacing(8)

        channel_card = QFrame()
        channel_card.setStyleSheet(card_style())
        channel_card_layout = QVBoxLayout(channel_card)
        channel_card_layout.setContentsMargins(12, 10, 12, 10)
        channel_card_layout.setSpacing(8)

        # Channel checkboxes in horizontal layout
        channel_row = QHBoxLayout()
        channel_row.setSpacing(12)

        self.sidebar.export_channel_checkboxes = []
        for ch in ["A", "B", "C", "D"]:
            ch_check = QCheckBox(f"Ch {ch}")
            ch_check.setChecked(True)
            ch_check.setStyleSheet(checkbox_style())
            self.sidebar.export_channel_checkboxes.append(ch_check)
            channel_row.addWidget(ch_check)

        channel_row.addStretch()
        channel_card_layout.addLayout(channel_row)

        # Select All button
        self.sidebar.select_all_channels_btn = QPushButton("Select All")
        self.sidebar.select_all_channels_btn.setFixedHeight(28)
        self.sidebar.select_all_channels_btn.setFixedWidth(100)
        self.sidebar.select_all_channels_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.SECONDARY_TEXT};"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-size: 11px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {Colors.OVERLAY_LIGHT_6};"
            f"}}",
        )
        self.sidebar.select_all_channels_btn.clicked.connect(
            self.sidebar._toggle_all_channels,
        )
        channel_card_layout.addWidget(self.sidebar.select_all_channels_btn)

        tab_layout.addWidget(channel_card)
        tab_layout.addSpacing(16)

    def _build_export_format(self, tab_layout: QVBoxLayout):
        """Build export format selection with radio buttons (Excel, CSV, JSON, HDF5)."""
        format_section = QLabel("EXPORT FORMAT")
        format_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(format_section)
        tab_layout.addSpacing(8)

        format_card = QFrame()
        format_card.setStyleSheet(card_style())
        format_card_layout = QVBoxLayout(format_card)
        format_card_layout.setContentsMargins(12, 10, 12, 10)
        format_card_layout.setSpacing(6)

        # Format radio buttons
        self.sidebar.format_group = QButtonGroup()

        radio_style = self._radio_button_style()

        self.sidebar.excel_radio = QRadioButton("Excel (.xlsx) - Multi-tab workbook")
        self.sidebar.excel_radio.setChecked(True)
        self.sidebar.excel_radio.setStyleSheet(radio_style)
        self.sidebar.format_group.addButton(self.sidebar.excel_radio)
        format_card_layout.addWidget(self.sidebar.excel_radio)

        self.sidebar.csv_radio = QRadioButton("CSV (.csv) - Single or multiple files")
        self.sidebar.csv_radio.setStyleSheet(radio_style)
        self.sidebar.format_group.addButton(self.sidebar.csv_radio)
        format_card_layout.addWidget(self.sidebar.csv_radio)

        self.sidebar.json_radio = QRadioButton("JSON (.json) - Structured data")
        self.sidebar.json_radio.setStyleSheet(radio_style)
        self.sidebar.format_group.addButton(self.sidebar.json_radio)
        format_card_layout.addWidget(self.sidebar.json_radio)

        self.sidebar.hdf5_radio = QRadioButton("HDF5 (.h5) - Large datasets")
        self.sidebar.hdf5_radio.setStyleSheet(radio_style)
        self.sidebar.format_group.addButton(self.sidebar.hdf5_radio)
        format_card_layout.addWidget(self.sidebar.hdf5_radio)

        tab_layout.addWidget(format_card)
        tab_layout.addSpacing(16)

    def _build_export_options(self, tab_layout: QVBoxLayout):
        """Build export options section (metadata, events, precision, timestamp format)."""
        options_section = QLabel("EXPORT OPTIONS")
        options_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(options_section)
        tab_layout.addSpacing(8)

        options_card = QFrame()
        options_card.setStyleSheet(card_style())
        options_card_layout = QVBoxLayout(options_card)
        options_card_layout.setContentsMargins(12, 10, 12, 10)
        options_card_layout.setSpacing(8)

        # Options checkboxes
        self.sidebar.metadata_check = QCheckBox(
            "Include Metadata (instrument settings, calibration)",
        )
        self.sidebar.metadata_check.setChecked(True)
        self.sidebar.metadata_check.setStyleSheet(checkbox_style())
        options_card_layout.addWidget(self.sidebar.metadata_check)

        self.sidebar.events_check = QCheckBox(
            "Include Event Markers (injection/wash/spike)",
        )
        self.sidebar.events_check.setChecked(False)
        self.sidebar.events_check.setStyleSheet(checkbox_style())
        options_card_layout.addWidget(self.sidebar.events_check)

        # Decimal precision
        precision_row = QHBoxLayout()
        precision_row.setSpacing(10)

        precision_label = QLabel("Decimal Precision:")
        precision_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        precision_row.addWidget(precision_label)

        self.sidebar.precision_combo = QComboBox()
        self.sidebar.precision_combo.addItems(["2", "3", "4", "5"])
        self.sidebar.precision_combo.setCurrentIndex(2)
        self.sidebar.precision_combo.setFixedWidth(80)
        self.sidebar.precision_combo.setStyleSheet(self._combo_style())
        precision_row.addWidget(self.sidebar.precision_combo)
        precision_row.addStretch()
        options_card_layout.addLayout(precision_row)

        # Timestamp format
        timestamp_row = QHBoxLayout()
        timestamp_row.setSpacing(10)

        timestamp_label = QLabel("Timestamp Format:")
        timestamp_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        timestamp_row.addWidget(timestamp_label)

        self.sidebar.timestamp_combo = QComboBox()
        self.sidebar.timestamp_combo.addItems(
            ["Relative (00:00:00)", "Absolute (datetime)", "Elapsed seconds"],
        )
        self.sidebar.timestamp_combo.setFixedWidth(180)
        self.sidebar.timestamp_combo.setStyleSheet(self._combo_style())
        timestamp_row.addWidget(self.sidebar.timestamp_combo)
        timestamp_row.addStretch()
        options_card_layout.addLayout(timestamp_row)

        tab_layout.addWidget(options_card)
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
        filename_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        file_card_layout.addWidget(filename_label)

        self.sidebar.export_filename_input = QLineEdit()
        self.sidebar.export_filename_input.setPlaceholderText(
            "experiment_20251120_143022",
        )
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

        # Export button
        self.sidebar.export_data_btn = QPushButton("📁 Export Data")
        self.sidebar.export_data_btn.setFixedHeight(40)
        self.sidebar.export_data_btn.setStyleSheet(primary_button_style())
        # Note: Connected in affilabs_core_ui.py to _on_export_data
        file_card_layout.addWidget(self.sidebar.export_data_btn)

        tab_layout.addWidget(file_card)
        tab_layout.addSpacing(16)

    def _build_quick_presets(self, tab_layout: QVBoxLayout):
        """Build quick export presets section with preset buttons (CSV, Analysis, Publication)."""
        presets_label = QLabel("Quick Export Presets")
        presets_label.setStyleSheet(
            label_style(13, Colors.SECONDARY_TEXT)
            + "font-weight: 600; margin-top: 4px;",
        )
        tab_layout.addWidget(presets_label)
        tab_layout.addSpacing(4)

        # Preset buttons
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)

        preset_btn_style = (
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-size: 12px;"
            f"  font-weight: 500;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
        )

        self.sidebar.quick_csv_btn = QPushButton("Quick CSV")
        self.sidebar.quick_csv_btn.setFixedHeight(32)
        self.sidebar.quick_csv_btn.setToolTip(
            "Fast CSV export with all data, no metadata (ideal for quick review)",
        )
        self.sidebar.quick_csv_btn.setStyleSheet(preset_btn_style)
        preset_row.addWidget(self.sidebar.quick_csv_btn)

        self.sidebar.analysis_btn = QPushButton("Analysis Ready")
        self.sidebar.analysis_btn.setFixedHeight(32)
        self.sidebar.analysis_btn.setToolTip(
            "Excel export with processed data, summary table, and metadata (ideal for analysis software)",
        )
        self.sidebar.analysis_btn.setStyleSheet(preset_btn_style)
        preset_row.addWidget(self.sidebar.analysis_btn)

        self.sidebar.publication_btn = QPushButton("Publication")
        self.sidebar.publication_btn.setFixedHeight(32)
        self.sidebar.publication_btn.setToolTip(
            "High-precision Excel export with all metadata (ideal for publications)",
        )
        self.sidebar.publication_btn.setStyleSheet(preset_btn_style)
        preset_row.addWidget(self.sidebar.publication_btn)

        preset_row.addStretch()
        tab_layout.addLayout(preset_row)

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
