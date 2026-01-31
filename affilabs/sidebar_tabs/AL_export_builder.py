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
    QInputDialog,
    QMessageBox,
)

from affilabs.services.user_profile_manager import UserProfileManager

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
        self.user_manager = UserProfileManager()

    def build(self, tab_layout: QVBoxLayout):
        """Build the complete Export tab UI.

        Args:
            tab_layout: QVBoxLayout to add export tab widgets to

        """
        self._build_user_profile(tab_layout)
        self._build_file_settings(tab_layout)
        # Export format hidden - only Excel format is used
        # Export options hidden - not currently used

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
        format_row.addWidget(self.sidebar.format_combo)
        format_row.addStretch()
        format_card_layout.addLayout(format_row)

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
        precision_label.setFixedWidth(120)
        precision_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        precision_row.addWidget(precision_label)

        self.sidebar.precision_combo = QComboBox()
        self.sidebar.precision_combo.addItems(["2", "3", "4", "5"])
        self.sidebar.precision_combo.setCurrentIndex(2)
        self.sidebar.precision_combo.setFixedWidth(70)
        self.sidebar.precision_combo.setStyleSheet(self._combo_style())
        precision_row.addWidget(self.sidebar.precision_combo)
        precision_row.addStretch()
        options_card_layout.addLayout(precision_row)

        # Timestamp format
        timestamp_row = QHBoxLayout()
        timestamp_row.setSpacing(10)

        timestamp_label = QLabel("Timestamp Format:")
        timestamp_label.setFixedWidth(120)
        timestamp_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        timestamp_row.addWidget(timestamp_label)

        self.sidebar.timestamp_combo = QComboBox()
        self.sidebar.timestamp_combo.addItems(
            ["Relative (00:00:00)", "Absolute (datetime)", "Elapsed seconds"],
        )
        self.sidebar.timestamp_combo.setFixedWidth(160)
        self.sidebar.timestamp_combo.setStyleSheet(self._combo_style())
        timestamp_row.addWidget(self.sidebar.timestamp_combo)
        timestamp_row.addStretch()
        options_card_layout.addLayout(timestamp_row)

        tab_layout.addWidget(options_card)
        tab_layout.addSpacing(16)

    def _build_user_profile(self, tab_layout: QVBoxLayout):
        """Build user profile section at top of export tab."""
        profile_section = QLabel("USER PROFILE")
        profile_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(profile_section)
        tab_layout.addSpacing(8)

        profile_card = QFrame()
        profile_card.setStyleSheet(card_style())
        profile_card_layout = QVBoxLayout(profile_card)
        profile_card_layout.setContentsMargins(12, 10, 12, 10)
        profile_card_layout.setSpacing(10)

        # User selection row
        user_row = QHBoxLayout()
        user_row.setSpacing(8)

        user_label = QLabel("Current User:")
        user_label.setFixedWidth(100)
        user_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        user_row.addWidget(user_label)

        self.sidebar.user_combo = QComboBox()
        self.sidebar.user_combo.addItems(self.user_manager.get_profiles())
        current_user = self.user_manager.get_current_user()
        if current_user:
            index = self.sidebar.user_combo.findText(current_user)
            if index >= 0:
                self.sidebar.user_combo.setCurrentIndex(index)
        self.sidebar.user_combo.setStyleSheet(self._combo_style())
        self.sidebar.user_combo.currentTextChanged.connect(self._on_user_changed)
        user_row.addWidget(self.sidebar.user_combo)

        # Add user button
        add_user_btn = QPushButton("+ Add")
        add_user_btn.setFixedWidth(60)
        add_user_btn.setFixedHeight(32)
        add_user_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: #34C759;"
            f"  color: white;"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  padding: 4px 8px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: #30B350; }}",
        )
        add_user_btn.clicked.connect(self._on_add_user)
        user_row.addWidget(add_user_btn)

        user_row.addStretch()
        profile_card_layout.addLayout(user_row)

        # Info label
        info_label = QLabel("💡 User name is saved in exported Excel metadata")
        info_label.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT)
            + "font-style: italic; margin-top: 4px;",
        )
        profile_card_layout.addWidget(info_label)

        tab_layout.addWidget(profile_card)
        tab_layout.addSpacing(16)

    def _on_user_changed(self, username: str):
        """Handle user selection change."""
        if username:
            self.user_manager.set_current_user(username)
            # Update filename with new user
            self._update_filename_with_user()

    def _on_add_user(self):
        """Handle add user button click."""
        from affilabs.utils.logger import logger
        logger.debug("Add user button clicked")
        username, ok = QInputDialog.getText(
            self.sidebar,
            "Add User Profile",
            "Enter user name:",
        )
        if ok and username:
            if self.user_manager.add_user(username):
                # Refresh dropdown
                self.sidebar.user_combo.clear()
                self.sidebar.user_combo.addItems(self.user_manager.get_profiles())
                # Select the new user
                index = self.sidebar.user_combo.findText(username)
                if index >= 0:
                    self.sidebar.user_combo.setCurrentIndex(index)
                QMessageBox.information(
                    self.sidebar,
                    "Success",
                    f"User '{username}' added successfully!",
                )
            else:
                QMessageBox.warning(
                    self.sidebar,
                    "User Exists",
                    f"User '{username}' already exists.",
                )

    def _update_filename_with_user(self):
        """Update filename to include current user."""
        if hasattr(self.sidebar, 'export_filename_input'):
            from affilabs.utils.time_utils import filename_timestamp
            current_user = self.user_manager.get_current_user()
            # Format: Username_data_timestamp
            user_clean = current_user.replace(' ', '_')
            new_filename = f"{user_clean}_data_{filename_timestamp()}"
            self.sidebar.export_filename_input.setText(new_filename)

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
        # Set default filename with user and timestamp
        from affilabs.utils.time_utils import filename_timestamp
        current_user = self.user_manager.get_current_user()
        user_clean = current_user.replace(' ', '_')
        default_name = f"{user_clean}_data_{filename_timestamp()}"
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

        # Send to Edits button
        file_card_layout.addSpacing(8)
        self.sidebar.send_to_edits_btn = QPushButton("📤 Send Live Data to Edits")
        self.sidebar.send_to_edits_btn.setFixedHeight(36)
        self.sidebar.send_to_edits_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: #34C759;"
            f"  color: white;"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  padding: 8px 16px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: #28A745; }}"
            f"QPushButton:disabled {{"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"}}"
        )
        self.sidebar.send_to_edits_btn.setToolTip(
            "Transfer current live recording data to Edits tab for review and modification"
        )
        # Note: Connected in affilabs_core_ui.py to _on_send_to_edits_clicked
        file_card_layout.addWidget(self.sidebar.send_to_edits_btn)
        file_card_layout.addSpacing(4)

        # Export button
        self.sidebar.export_data_btn = QPushButton("📁 Export Data")
        self.sidebar.export_data_btn.setFixedHeight(40)
        self.sidebar.export_data_btn.setStyleSheet(primary_button_style())
        # Note: Connected in affilabs_core_ui.py to _on_export_data
        file_card_layout.addWidget(self.sidebar.export_data_btn)

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
