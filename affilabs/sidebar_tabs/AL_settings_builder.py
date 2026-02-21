"""Settings Tab Builder

Handles building the Settings tab UI with hardware config and calibration controls.

Author: Affilabs
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QInputDialog,
)

# Import sections from central location
from affilabs.sections import CollapsibleSection
from affilabs.ui_styles import (
    Colors,
    Fonts,
    card_style,
    checkbox_style,
    label_style,
    section_header_style,
)
from affilabs.services.user_profile_manager import UserProfileManager

# Colorblind-safe palette (Tol bright scheme)
COLORBLIND_PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44"]


class SettingsTabBuilder:
    """Builder for constructing the Settings tab UI with diagnostics, hardware config, and calibration."""

    def __init__(self, sidebar):
        """Initialize builder with reference to parent sidebar.

        Args:
            sidebar: Parent AffilabsSidebar instance to attach widgets to

        """
        self.sidebar = sidebar
        # Use shared instance from sidebar (will be set by main app)
        self.user_manager = None

    def build(self, tab_layout: QVBoxLayout):
        """Build the complete Settings tab UI.

        Args:
            tab_layout: QVBoxLayout to add settings tab widgets to

        """
        # Intelligence bar removed for cleaner UI
        # self._build_intelligence_bar(tab_layout)
        self._build_hardware_configuration(tab_layout)
        self._build_calibration_controls(tab_layout)

        # Display Controls (moved from Graphic Control tab)
        self._build_display_controls_section(tab_layout)

        # Spectroscopy plots moved to LiveContextPanel (Phase 3 sidebar redesign).
        # Previously: self._build_spectroscopy_plots(tab_layout)
        # Plots now live in affilabs/widgets/live_context_panel.py alongside the sensorgram.

        # Phase 5: Hardware Status section (replaces Device Status tab)
        self._build_hardware_status_section(tab_layout)

        # Phase 4: Minimal user management (add/rename/delete only — profile card in User+Export tab)
        self._build_manage_users_section(tab_layout)

        tab_layout.addSpacing(20)

    def _build_hardware_status_section(self, tab_layout: QVBoxLayout):
        """Phase 5: Embed Device Status widgets in Settings > Hardware Status (collapsed)."""
        from sections import CollapsibleSection
        from affilabs.sidebar_tabs.AL_device_status_builder import DeviceStatusTabBuilder

        hw_section = CollapsibleSection("🔌 Hardware Status", is_expanded=False)
        hw_section.content_layout.setSpacing(8)

        # Run the Device Status builder into this section's layout.
        # This populates sidebar.scan_btn, sidebar.add_hardware_btn, sidebar.debug_log_btn,
        # sidebar.subunit_status, sidebar.operation_modes, sidebar.hw_led_bar, etc.
        try:
            ds_builder = DeviceStatusTabBuilder(self.sidebar)
            ds_builder.build(hw_section.content_layout)
        except Exception as _e:
            from affilabs.utils.logger import logger
            logger.error(f"DeviceStatusTabBuilder failed in Settings: {_e}", exc_info=True)
            # Minimal fallback so subunit_status exists
            self.sidebar.subunit_status = {}
            self.sidebar.scan_btn = QPushButton("Scan")
            self.sidebar.scan_btn.setProperty("scanning", False)
            self.sidebar.add_hardware_btn = QPushButton("+ Add Hardware")
            self.sidebar.debug_log_btn = QPushButton("Debug Log")

        tab_layout.addWidget(hw_section)

    def _build_manage_users_section(self, tab_layout: QVBoxLayout):
        """Phase 4: Minimal user management — add / rename / delete only (no progression display)."""
        from sections import CollapsibleSection

        mgmt_section = CollapsibleSection("👥 Manage Users", is_expanded=False)

        _help = QLabel("Add, rename, or remove lab users")
        _help.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent;"
            "font-style: italic; margin: 4px 0 8px 0;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        mgmt_section.content_layout.addWidget(_help)

        _card = QFrame()
        _card.setStyleSheet("QFrame { background: rgba(0,0,0,0.03); border-radius: 8px; }")
        _card_layout = QVBoxLayout(_card)
        _card_layout.setContentsMargins(12, 8, 12, 8)
        _card_layout.setSpacing(8)

        self.sidebar.user_list_widget = QListWidget()
        self.sidebar.user_list_widget.setMaximumHeight(110)
        self.sidebar.user_list_widget.setStyleSheet(
            "QListWidget { background: white; border: 1px solid rgba(0,0,0,0.08);"
            "  border-radius: 6px; padding: 4px; font-size: 13px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif; }"
            "QListWidget::item { padding: 6px 8px; border-radius: 4px; }"
            "QListWidget::item:selected { background: rgba(0,122,255,0.12); }"
        )
        self._populate_user_list()
        self.sidebar.user_list_widget.itemDoubleClicked.connect(self._on_set_active_user_settings)
        _card_layout.addWidget(self.sidebar.user_list_widget)

        _btn_row = QHBoxLayout()
        _btn_row.setSpacing(6)

        def _mini_btn(label, color):
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color};"
                f"  border: 1px solid {color}44; border-radius: 6px;"
                f"  padding: 3px 8px; font-size: 11px; font-weight: 600;"
                f"  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif; }}"
                f"QPushButton:hover {{ background: {color}18; }}"
            )
            return b

        _add_btn = _mini_btn("+ Add", "#34C759")
        _add_btn.clicked.connect(self._on_add_user_settings)
        _btn_row.addWidget(_add_btn)

        _rename_btn = _mini_btn("Rename", "#007AFF")
        _rename_btn.clicked.connect(self._on_rename_user_settings)
        _btn_row.addWidget(_rename_btn)

        _active_btn = _mini_btn("Set Active", "#FF9500")
        _active_btn.clicked.connect(lambda: self._on_set_active_user_settings())
        _btn_row.addWidget(_active_btn)

        _del_btn = _mini_btn("Delete", "#FF3B30")
        _del_btn.clicked.connect(self._on_delete_user_settings)
        _btn_row.addWidget(_del_btn)

        _card_layout.addLayout(_btn_row)
        mgmt_section.add_content_widget(_card)
        tab_layout.addWidget(mgmt_section)

    def _build_user_management(self, tab_layout: QVBoxLayout):
        """Build user management section with progression display."""
        # Get shared user manager from sidebar (set by main app)
        if hasattr(self.sidebar, 'user_profile_manager') and self.sidebar.user_profile_manager:
            self.user_manager = self.sidebar.user_profile_manager

        user_mgmt_section = CollapsibleSection(
            "👥 User Management",
            is_expanded=False,
        )

        user_mgmt_help = QLabel("Manage lab users who can run experiments")
        user_mgmt_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        user_mgmt_section.content_layout.addWidget(user_mgmt_help)

        user_mgmt_card = QFrame()
        user_mgmt_card.setStyleSheet(
            f"QFrame {{"
            f"  background: rgba(0, 0, 0, 0.03);"
            f"  border-radius: 8px;"
            f"}}"
        )
        user_mgmt_layout = QVBoxLayout(user_mgmt_card)
        user_mgmt_layout.setContentsMargins(12, 8, 12, 8)
        user_mgmt_layout.setSpacing(8)

        # ── Current user progression banner ──
        self.sidebar.user_progression_frame = QFrame()
        self.sidebar.user_progression_frame.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 122, 255, 0.06);"
            "  border-radius: 8px;"
            "}"
        )
        prog_layout = QVBoxLayout(self.sidebar.user_progression_frame)
        prog_layout.setContentsMargins(10, 8, 10, 8)
        prog_layout.setSpacing(4)

        self.sidebar.user_title_label = QLabel("")
        self.sidebar.user_title_label.setStyleSheet(
            f"font-size: 14px;"
            f"color: #007AFF;"
            f"font-weight: 700;"
            f"background: transparent;"
            f"font-family: {Fonts.SYSTEM};"
        )
        prog_layout.addWidget(self.sidebar.user_title_label)

        self.sidebar.user_xp_label = QLabel("")
        self.sidebar.user_xp_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {Colors.SECONDARY_TEXT};"
            f"font-weight: 400;"
            f"background: transparent;"
            f"font-family: {Fonts.SYSTEM};"
        )
        prog_layout.addWidget(self.sidebar.user_xp_label)

        self.sidebar.user_training_label = QLabel("")
        self.sidebar.user_training_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {Colors.SECONDARY_TEXT};"
            f"font-weight: 400;"
            f"background: transparent;"
            f"font-family: {Fonts.SYSTEM};"
        )
        prog_layout.addWidget(self.sidebar.user_training_label)

        user_mgmt_layout.addWidget(self.sidebar.user_progression_frame)

        # Update progression display for current user
        self._update_progression_display()

        # ── User list ──
        users_label = QLabel("Current Users:")
        users_label.setStyleSheet(
            f"font-size: 12px;"
            f"color: {Colors.SECONDARY_TEXT};"
            f"font-weight: 500;"
            f"background: transparent;"
            f"font-family: {Fonts.SYSTEM};"
        )
        user_mgmt_layout.addWidget(users_label)

        self.sidebar.user_list_widget = QListWidget()
        self._populate_user_list()
        self.sidebar.user_list_widget.setMaximumHeight(120)
        self.sidebar.user_list_widget.itemDoubleClicked.connect(
            self._on_set_active_user_settings
        )
        self.sidebar.user_list_widget.setStyleSheet(
            f"QListWidget {{"
            f"  background: {Colors.BACKGROUND_LIGHT};"
            f"  border: 1px solid rgba(0, 0, 0, 0.08);"
            f"  border-radius: 6px;"
            f"  padding: 4px;"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 6px 8px;"
            f"  border-radius: 4px;"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background: {Colors.OVERLAY_LIGHT_6};"
            f"}}"
        )
        user_mgmt_layout.addWidget(self.sidebar.user_list_widget)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        add_user_btn = QPushButton("+ Add User")
        add_user_btn.setFixedHeight(32)
        add_user_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: #34C759;"
            f"  color: white;"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: #30B350; }}"
            f"QPushButton:pressed {{ background: #2A9E47; }}"
        )
        add_user_btn.clicked.connect(self._on_add_user_settings)
        btn_row.addWidget(add_user_btn)

        rename_user_btn = QPushButton("Rename")
        rename_user_btn.setFixedHeight(32)
        rename_user_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: transparent;"
            f"  color: #007AFF;"
            f"  border: 1px solid rgba(0, 122, 255, 0.35);"
            f"  border-radius: 6px;"
            f"  padding: 4px 10px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: rgba(0, 122, 255, 0.10);"
            f"  border-color: #007AFF;"
            f"}}"
        )
        rename_user_btn.clicked.connect(self._on_rename_user_settings)
        btn_row.addWidget(rename_user_btn)

        set_active_btn = QPushButton("Set Active")
        set_active_btn.setFixedHeight(32)
        set_active_btn.setToolTip("Set selected user as the current active user (double-click also works)")
        set_active_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: transparent;"
            f"  color: #FF9500;"
            f"  border: 1px solid rgba(255, 149, 0, 0.35);"
            f"  border-radius: 6px;"
            f"  padding: 4px 10px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: rgba(255, 149, 0, 0.10);"
            f"  border-color: #FF9500;"
            f"}}"
        )
        set_active_btn.clicked.connect(lambda: self._on_set_active_user_settings())
        btn_row.addWidget(set_active_btn)

        delete_user_btn = QPushButton("Delete")
        delete_user_btn.setFixedHeight(32)
        delete_user_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: transparent;"
            f"  color: #FF3B30;"
            f"  border: 1px solid rgba(255, 59, 48, 0.3);"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: rgba(255, 59, 48, 0.1);"
            f"  border-color: #FF3B30;"
            f"}}"
        )
        delete_user_btn.clicked.connect(self._on_delete_user_settings)
        btn_row.addWidget(delete_user_btn)

        user_mgmt_layout.addLayout(btn_row)

        user_mgmt_section.add_content_widget(user_mgmt_card)
        tab_layout.addWidget(user_mgmt_section)

    def _populate_user_list(self):
        """Populate user list widget with names and progression titles."""
        # Check if user_manager is available (may not be set during initial UI construction)
        if not self.user_manager:
            return

        current = self.user_manager.get_current_user()
        self.sidebar.user_list_widget.clear()
        for username in self.user_manager.get_profiles():
            title, _ = self.user_manager.get_title(username)
            exp_count = self.user_manager.get_experiment_count(username)

            is_active = username == current
            marker = "★ " if is_active else "   "
            display = (
                f"{marker}{username}  \u2014  {title.value} "
                f"({exp_count} experiments)"
            )

            item = QListWidgetItem(display)
            if is_active:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.GlobalColor.blue)
            self.sidebar.user_list_widget.addItem(item)

    def _update_progression_display(self):
        """Update the progression banner for the current user."""
        # Check if user_manager is available (may not be set during initial UI construction)
        if not self.user_manager:
            # Hide progression frame when no user manager
            if hasattr(self.sidebar, 'user_progression_frame'):
                self.sidebar.user_progression_frame.setVisible(False)
            return

        current = self.user_manager.get_current_user()
        if not current:
            # Hide progression frame when no current user
            if hasattr(self.sidebar, 'user_progression_frame'):
                self.sidebar.user_progression_frame.setVisible(False)
            return

        # Show progression frame when we have user data
        if hasattr(self.sidebar, 'user_progression_frame'):
            self.sidebar.user_progression_frame.setVisible(True)

        # Footer passive user indicator
        if hasattr(self.sidebar, 'active_user_label'):
            self.sidebar.active_user_label.setText(f"Running as: {current}")

        summary = self.user_manager.get_progression_summary(current)

        # Title line (widget now lives in User+Export tab)
        if hasattr(self.sidebar, 'user_title_label'):
            title = summary['title']
            self.sidebar.user_title_label.setText(f"👤 {current}  •  {title}")

        # XP & next title
        if hasattr(self.sidebar, 'user_xp_label'):
            xp = summary['xp']
            next_title = summary['next_title']
            remaining = summary['experiments_to_next_title']
            if next_title:
                self.sidebar.user_xp_label.setText(
                    f"XP: {xp}  •  {remaining} experiments to {next_title}"
                )
            else:
                self.sidebar.user_xp_label.setText(f"XP: {xp}  •  Maximum rank achieved!")

        # Training status — no longer required per user
        if hasattr(self.sidebar, 'user_training_label'):
            self.sidebar.user_training_label.hide()

    def _on_add_user_settings(self):
        """Handle adding a new user from settings."""
        # Lazy-resolve user manager if not yet set
        if not self.user_manager and hasattr(self.sidebar, 'user_profile_manager'):
            self.user_manager = self.sidebar.user_profile_manager
        if not self.user_manager:
            QMessageBox.warning(self.sidebar, "Not Ready", "User manager is not available yet. Please wait for the application to fully load.")
            return

        username, ok = QInputDialog.getText(
            self.sidebar,
            "Add User",
            "Enter user name:",
        )
        if ok and username:
            username = username.strip()
            if not username:
                QMessageBox.warning(
                    self.sidebar,
                    "Invalid Name",
                    "User name cannot be empty.",
                )
                return

            if self.user_manager.add_user(username):
                # Update list widget with titles
                self._populate_user_list()
                # Update progression display
                self._update_progression_display()
                # Update dropdown in Method Builder if it exists
                if hasattr(self.sidebar, 'user_combo'):
                    current = self.sidebar.user_combo.currentText()
                    self.sidebar.user_combo.clear()
                    self.sidebar.user_combo.addItems(
                        self.user_manager.get_profiles()
                    )
                    idx = self.sidebar.user_combo.findText(current)
                    if idx >= 0:
                        self.sidebar.user_combo.setCurrentIndex(idx)

                # Inform user
                QMessageBox.information(
                    self.sidebar,
                    "User Created",
                    f"User '{username}' has been created.",
                )
            else:
                QMessageBox.warning(
                    self.sidebar,
                    "User Exists",
                    f"User '{username}' already exists.",
                )

    def _on_delete_user_settings(self):
        """Handle deleting selected user from settings."""
        # Lazy-resolve user manager if not yet set
        if not self.user_manager and hasattr(self.sidebar, 'user_profile_manager'):
            self.user_manager = self.sidebar.user_profile_manager
        if not self.user_manager:
            QMessageBox.warning(self.sidebar, "Not Ready", "User manager is not available yet. Please wait for the application to fully load.")
            return

        selected_items = self.sidebar.user_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self.sidebar,
                "No Selection",
                "Please select a user to delete.",
            )
            return

        # Extract username from display text (format: "★ username  —  Title (...)")
        username = self._extract_username_from_item(selected_items[0].text())

        # Confirm deletion
        reply = QMessageBox.question(
            self.sidebar,
            "Confirm Delete",
            f"Delete user '{username}' and all progression data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.user_manager.remove_user(username):
                # Update list widget with titles
                self._populate_user_list()
                # Update progression display
                self._update_progression_display()
                # Update dropdown in Method Builder if it exists
                if hasattr(self.sidebar, 'user_combo'):
                    self.sidebar.user_combo.clear()
                    self.sidebar.user_combo.addItems(
                        self.user_manager.get_profiles()
                    )
                    # Set to current user
                    current = self.user_manager.get_current_user()
                    if current:
                        idx = self.sidebar.user_combo.findText(current)
                        if idx >= 0:
                            self.sidebar.user_combo.setCurrentIndex(idx)
            else:
                QMessageBox.warning(
                    self.sidebar,
                    "Cannot Delete",
                    "You must keep at least one user profile.",
                )

    def _extract_username_from_item(self, display_text: str) -> str:
        """Extract plain username from list item display text.

        Handles formats: '★ username  —  Title (N experiments)'
        and '   username  —  Title (N experiments)'.
        """
        clean = display_text.lstrip("\u2605 ").strip()
        return clean.split("  \u2014  ")[0].strip()

    def _on_rename_user_settings(self):
        """Handle renaming the selected user."""
        if not self.user_manager and hasattr(self.sidebar, 'user_profile_manager'):
            self.user_manager = self.sidebar.user_profile_manager
        if not self.user_manager:
            QMessageBox.warning(self.sidebar, "Not Ready", "User manager is not available yet.")
            return

        selected_items = self.sidebar.user_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self.sidebar, "No Selection", "Please select a user to rename.")
            return

        old_name = self._extract_username_from_item(selected_items[0].text())

        new_name, ok = QInputDialog.getText(
            self.sidebar,
            "Rename User",
            f"New name for '{old_name}':",
            text=old_name,
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        if self.user_manager.rename_user(old_name, new_name):
            self._populate_user_list()
            self._update_progression_display()
            if hasattr(self.sidebar, 'user_combo'):
                current = self.user_manager.get_current_user()
                self.sidebar.user_combo.clear()
                self.sidebar.user_combo.addItems(self.user_manager.get_profiles())
                if current:
                    idx = self.sidebar.user_combo.findText(current)
                    if idx >= 0:
                        self.sidebar.user_combo.setCurrentIndex(idx)
        else:
            QMessageBox.warning(
                self.sidebar,
                "Rename Failed",
                f"Could not rename to '{new_name}'. Name may already be in use.",
            )

    def _on_set_active_user_settings(self, item=None):
        """Set the selected (or double-clicked) user as the currently active user."""
        if not self.user_manager and hasattr(self.sidebar, 'user_profile_manager'):
            self.user_manager = self.sidebar.user_profile_manager
        if not self.user_manager:
            return

        if item is None:
            selected_items = self.sidebar.user_list_widget.selectedItems()
            if not selected_items:
                QMessageBox.information(
                    self.sidebar,
                    "No Selection",
                    "Please select a user to set as active.",
                )
                return
            item = selected_items[0]

        username = self._extract_username_from_item(item.text())
        self.user_manager.set_current_user(username)
        self._populate_user_list()
        self._update_progression_display()
        if hasattr(self.sidebar, 'user_combo'):
            idx = self.sidebar.user_combo.findText(username)
            if idx >= 0:
                self.sidebar.user_combo.setCurrentIndex(idx)

    def _create_spectroscopy_placeholder(self, tab_layout: QVBoxLayout):
        """Create placeholder for spectroscopy plots - will be lazy loaded on tab open."""
        from sections import CollapsibleSection

        spectro_section = CollapsibleSection("📊 Live Spectroscopy", is_expanded=True)

        # Store reference for lazy loading
        self.sidebar._spectroscopy_section = spectro_section
        self.sidebar._spectroscopy_tab_layout = tab_layout

        spectro_help = QLabel("Plots will load when you open this tab")
        spectro_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        spectro_section.content_layout.addWidget(spectro_help)

        tab_layout.addWidget(spectro_section)

        # Store placeholder reference
        self.sidebar._spectroscopy_placeholder = spectro_section

    def _build_spectroscopy_plots(self, tab_layout: QVBoxLayout):
        """Build lean spectroscopy plots for QC troubleshooting."""
        from plot_helpers import add_channel_curves, create_spectroscopy_plot
        from sections import CollapsibleSection

        from affilabs.utils.logger import logger

        logger.debug("Building spectroscopy plots in Settings tab...")
        spectro_section = CollapsibleSection("📊 Live Spectroscopy", is_expanded=True)

        spectro_help = QLabel(
            "Real-time transmission and raw detector spectrum display",
        )
        spectro_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        spectro_section.content_layout.addWidget(spectro_help)

        # Card container
        spectro_card = QFrame()
        spectro_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        spectro_card_layout = QVBoxLayout(spectro_card)
        spectro_card_layout.setContentsMargins(12, 8, 12, 8)
        spectro_card_layout.setSpacing(8)

        # Transmission Plot
        trans_label = QLabel("Transmission Spectrum (%):")
        trans_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        spectro_card_layout.addWidget(trans_label)

        # Create lean transmission plot (for troubleshooting)
        self.sidebar.transmission_plot = create_spectroscopy_plot(
            left_label="Transmission (norm.)",
            bottom_label="Wavelength (nm)",
        )
        self.sidebar.transmission_plot.setFixedHeight(180)  # Lean fixed height
        self.sidebar.transmission_plot.setMinimumHeight(180)
        spectro_card_layout.addWidget(self.sidebar.transmission_plot)

        # Add channel curves to transmission plot
        self.sidebar.transmission_curves = add_channel_curves(
            self.sidebar.transmission_plot,
        )

        # Add "Capture Baseline" button (REBUILT - cleaner architecture)
        baseline_btn = QPushButton("[REC] Capture 5-Min Baseline")
        baseline_btn.setObjectName("baseline_capture_btn")  # Explicit object name
        baseline_btn.setFixedHeight(28)
        baseline_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        baseline_btn.setStyleSheet(
            "QPushButton#baseline_capture_btn {"
            "  background-color: #F2F2F7;"
            "  color: #666666;"
            "  border: 1px solid #E5E5EA;"
            "  border-radius: 6px;"
            "  padding: 4px 10px;"
            "  font-size: 11px;"
            "  font-weight: normal;"
            "}"
            "QPushButton#baseline_capture_btn:hover {"
            "  background-color: #E8E8ED;"
            "  border: 1px solid #D5D5DA;"
            "}"
            "QPushButton#baseline_capture_btn:pressed {"
            "  background-color: #DADADF;"
            "}"
            "QPushButton#baseline_capture_btn:disabled {"
            "  background-color: #F5F5F7;"
            "  color: #C7C7CC;"
            "  border: 1px solid #E5E5EA;"
            "}",
        )
        baseline_btn.setToolTip(
            "Capture 5 minutes of baseline transmission data\n"
            "for noise analysis and optimization.\n\n"
            "Requirements:\n"
            "• Stable baseline (no injections)\n"
            "• Live acquisition running\n"
            "• System calibrated",
        )
        self.sidebar.baseline_capture_btn = baseline_btn
        spectro_card_layout.addWidget(baseline_btn)

        spectro_card_layout.addSpacing(12)

        # Raw Data Plot
        raw_label = QLabel("Raw Detector Signal (counts):")
        raw_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        spectro_card_layout.addWidget(raw_label)

        # Create lean raw data plot (for troubleshooting)
        self.sidebar.raw_data_plot = create_spectroscopy_plot(
            left_label="Intensity (counts)",
            bottom_label="Wavelength (nm)",
        )
        self.sidebar.raw_data_plot.setFixedHeight(180)  # Lean fixed height
        self.sidebar.raw_data_plot.setMinimumHeight(180)
        spectro_card_layout.addWidget(self.sidebar.raw_data_plot)

        # Add channel curves to raw data plot
        self.sidebar.raw_data_curves = add_channel_curves(self.sidebar.raw_data_plot)

        spectro_section.add_content_widget(spectro_card)

        # Add to layout
        tab_layout.addWidget(spectro_section)

        # Store references for later access
        self.sidebar.spectro_section = spectro_section
        self.sidebar.spectro_card = spectro_card

        logger.debug(
            f"✓ Spectroscopy plots: transmission={len(self.sidebar.transmission_curves)}, raw={len(self.sidebar.raw_data_curves)}",
        )

    def _build_intelligence_bar(self, tab_layout: QVBoxLayout):
        """Build intelligence bar section."""
        intel_section = QLabel("INTELLIGENCE BAR")
        intel_section.setFixedHeight(15)
        intel_section.setStyleSheet(section_header_style())
        intel_section.setToolTip(
            "Real-time system status and guidance powered by AI diagnostics",
        )
        tab_layout.addWidget(intel_section)
        tab_layout.addSpacing(8)

        intel_bar = QFrame()
        intel_bar.setGeometry(20, 142, 411, 37)
        intel_bar.setStyleSheet(
            "QFrame {  background: transparent;  border: none;}",
        )
        intel_bar_layout = QHBoxLayout(intel_bar)
        intel_bar_layout.setContentsMargins(16, 12, 16, 8)
        intel_bar_layout.setSpacing(12)

        # Status indicators
        self.sidebar.settings_intel_status_label = QLabel("✓ Good")
        self.sidebar.settings_intel_status_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #34C759;"
            "  background: transparent;"
            "  font-weight: 700;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        intel_bar_layout.addWidget(self.sidebar.settings_intel_status_label)

        # Separator bullet
        self.sidebar.settings_intel_separator = QLabel("•")
        self.sidebar.settings_intel_separator.setStyleSheet(
            "QLabel { font-size: 12px; color: #86868B; background: transparent; }",
        )
        intel_bar_layout.addWidget(self.sidebar.settings_intel_separator)

        self.sidebar.settings_intel_message_label = QLabel("→ Hardware configured")
        self.sidebar.settings_intel_message_label.setFixedHeight(22)
        self.sidebar.settings_intel_message_label.setStyleSheet(
            "QLabel {"
            "  font-size: 14px;"
            "  color: #007AFF;"
            "  background: transparent;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        intel_bar_layout.addWidget(self.sidebar.settings_intel_message_label)

        intel_bar_layout.addStretch()

        tab_layout.addWidget(intel_bar)
        tab_layout.addSpacing(8)

    def _build_hardware_configuration(self, tab_layout: QVBoxLayout):
        """Build hardware configuration section with polarizer and LED settings (collapsible, starts expanded)."""
        hardware_section = CollapsibleSection(
            "⚙ Hardware Configuration",
            is_expanded=False,
        )

        hardware_help = QLabel(
            "Configure polarizer positions and LED intensity for each channel",
        )
        hardware_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        hardware_section.content_layout.addWidget(hardware_help)

        # Card container
        polarizer_led_card = QFrame()
        polarizer_led_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        polarizer_led_card_layout = QVBoxLayout(polarizer_led_card)
        polarizer_led_card_layout.setContentsMargins(12, 8, 12, 8)
        polarizer_led_card_layout.setSpacing(6)

        # Build sections
        self._build_polarizer_settings(polarizer_led_card_layout)
        self._add_separator(polarizer_led_card_layout)
        # Pipeline selector REMOVED - only Fourier method used in production
        self._build_led_settings(polarizer_led_card_layout)
        self._add_separator(polarizer_led_card_layout)
        # Detector wait time moved to Advanced Settings dialog
        self._build_settings_buttons(polarizer_led_card_layout)

        hardware_section.add_content_widget(polarizer_led_card)
        tab_layout.addWidget(hardware_section)

    def _build_polarizer_settings(self, layout: QVBoxLayout):
        """Build polarizer position settings (S/P positions and toggle button)."""
        polarizer_label = QLabel("Polarizer Positions:")
        polarizer_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        layout.addWidget(polarizer_label)

        polarizer_row = QHBoxLayout()
        polarizer_row.setSpacing(12)

        # S Position
        s_position_label = QLabel("S:")
        s_position_label.setStyleSheet(self._small_label_style())
        polarizer_row.addWidget(s_position_label)

        self.sidebar.s_position_input = QLineEdit()
        self.sidebar.s_position_input.setPlaceholderText("0-255")
        self.sidebar.s_position_input.setToolTip(
            "Servo position for S polarization mode (0-255 PWM)",
        )
        self.sidebar.s_position_input.setFixedWidth(70)
        self.sidebar.s_position_input.setStyleSheet(self._lineedit_style())
        # Connect to sync with device_config when changed
        self.sidebar.s_position_input.textChanged.connect(
            lambda text: self._on_s_position_changed(text),
        )
        polarizer_row.addWidget(self.sidebar.s_position_input)

        polarizer_row.addSpacing(16)

        # P Position
        p_position_label = QLabel("P:")
        p_position_label.setStyleSheet(self._small_label_style())
        polarizer_row.addWidget(p_position_label)

        self.sidebar.p_position_input = QLineEdit()
        self.sidebar.p_position_input.setPlaceholderText("0-255")
        self.sidebar.p_position_input.setToolTip(
            "Servo position for P polarization mode (0-255 PWM)",
        )
        self.sidebar.p_position_input.setFixedWidth(70)
        self.sidebar.p_position_input.setStyleSheet(self._lineedit_style())
        # Connect to sync with device_config when changed
        self.sidebar.p_position_input.textChanged.connect(
            lambda text: self._on_p_position_changed(text),
        )
        polarizer_row.addWidget(self.sidebar.p_position_input)

        # Toggle S/P Button
        self.sidebar.polarizer_toggle_btn = QPushButton("Position: S")
        self.sidebar.polarizer_toggle_btn.setFixedWidth(100)
        self.sidebar.polarizer_toggle_btn.setFixedHeight(28)
        self.sidebar.polarizer_toggle_btn.setToolTip(
            "Click to toggle between S and P polarization modes",
        )
        self.sidebar.polarizer_toggle_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}",
        )
        # Track current polarizer position on sidebar
        self.sidebar.current_polarizer_position = "S"
        polarizer_row.addWidget(self.sidebar.polarizer_toggle_btn)

        polarizer_row.addStretch()
        layout.addLayout(polarizer_row)

    def _build_led_settings(self, layout: QVBoxLayout):
        """Build LED brightness settings for channels A, B, C, D."""
        led_brightness_label = QLabel("LED Brightness per Channel:")
        led_brightness_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        layout.addWidget(led_brightness_label)

        # Create channel inputs (A, B, C, D)
        channels = ["a", "b", "c", "d"]
        for channel in channels:
            channel_row = QHBoxLayout()
            channel_row.setSpacing(10)

            channel_label = QLabel(f"Channel {channel.upper()}:")
            channel_label.setFixedWidth(70)
            channel_label.setStyleSheet(
                "QLabel {"
                "  font-size: 12px;"
                "  color: #1D1D1F;"
                "  background: transparent;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}",
            )
            channel_row.addWidget(channel_label)

            channel_input = QLineEdit()
            channel_input.setPlaceholderText("0-255")
            channel_input.setToolTip(
                f"LED brightness for Channel {channel.upper()} (0-255) - Changes apply immediately",
            )
            channel_input.setFixedWidth(70)
            channel_input.setStyleSheet(self._lineedit_style())
            channel_row.addWidget(channel_input)

            # Store reference on sidebar
            setattr(self.sidebar, f"channel_{channel}_input", channel_input)

            # Connect to live update handler
            # Emit signal with channel letter when text changes
            channel_input.textChanged.connect(
                lambda text, ch=channel: self.sidebar.led_brightness_changed.emit(ch, text)
            )

            channel_row.addStretch()
            layout.addLayout(channel_row)

    # Detector wait time moved to Advanced Settings dialog (Nov 2024)

    def _build_settings_buttons(self, layout: QVBoxLayout):
        """Build settings action buttons (Load Current, Apply Settings, Advanced)."""
        settings_button_row = QHBoxLayout()
        settings_button_row.setSpacing(8)

        # Apply Settings button
        self.sidebar.apply_settings_btn = QPushButton("Apply Settings")
        self.sidebar.apply_settings_btn.setFixedHeight(32)
        self.sidebar.apply_settings_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}",
        )
        settings_button_row.addWidget(self.sidebar.apply_settings_btn)

        # Advanced Settings button (gear icon)
        self.sidebar.advanced_settings_btn = QPushButton("⚙")
        self.sidebar.advanced_settings_btn.setFixedSize(32, 32)
        self.sidebar.advanced_settings_btn.setToolTip("Advanced Settings")
        self.sidebar.advanced_settings_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #86868B;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  font-size: 16px;"
            "  padding: 0px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  color: #1D1D1F;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(0, 0, 0, 0.15);"
            "}",
        )
        settings_button_row.addWidget(self.sidebar.advanced_settings_btn)

        layout.addLayout(settings_button_row)

    def _build_calibration_controls(self, tab_layout: QVBoxLayout):
        """Build calibration controls section with Simple, Full, and OEM calibrations (collapsible, starts collapsed)."""
        calibration_section = CollapsibleSection(
            "🔧 Calibration Controls",
            is_expanded=False,
        )

        calibration_help = QLabel(
            "Perform LED and system calibrations for optimal performance",
        )
        calibration_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        calibration_section.content_layout.addWidget(calibration_help)

        # Card container
        calibration_card = QFrame()
        calibration_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        calibration_card_layout = QVBoxLayout(calibration_card)
        calibration_card_layout.setContentsMargins(12, 8, 12, 8)
        calibration_card_layout.setSpacing(6)

        # Simple LED Calibration
        self._add_calibration_option(
            calibration_card_layout,
            title="Simple LED Calibration",
            description="Quick LED intensity adjustment for all channels",
            button_text="Run Simple Calibration",
            button_ref="simple_led_calibration_btn",
            primary=True,
        )

        calibration_card_layout.addSpacing(12)

        # Full System Calibration
        self._add_calibration_option(
            calibration_card_layout,
            title="Full System Calibration",
            description="Complete calibration including dark reference and LED optimization",
            button_text="Run Full Calibration",
            button_ref="full_calibration_btn",
            primary=False,
        )

        calibration_card_layout.addSpacing(12)

        # Polarizer Calibration
        self._add_calibration_option(
            calibration_card_layout,
            title="Polarizer Calibration",
            description="Find optimal servo positions for S and P modes (~90° apart, 1.4 min)",
            button_text="Calibrate Polarizer",
            button_ref="polarizer_calibration_btn",
            primary=False,
        )

        calibration_card_layout.addSpacing(12)

        # OEM LED Calibration
        self._add_calibration_option(
            calibration_card_layout,
            title="OEM LED Calibration",
            description="Factory-level calibration for LED driver settings (advanced users)",
            button_text="Run OEM Calibration",
            button_ref="oem_led_calibration_btn",
            primary=False,
        )

        calibration_card_layout.addSpacing(12)

        # LED Model Training Only
        self._add_calibration_option(
            calibration_card_layout,
            title="LED Model Training",
            description="Rebuild optical model only (10-60ms measurements, ~2 min)",
            button_text="Train LED Model",
            button_ref="led_model_training_btn",
            primary=False,
        )

        calibration_section.add_content_widget(calibration_card)
        tab_layout.addWidget(calibration_section)

        # Note: polarizer_toggle_btn.clicked and calibration buttons should be connected
        # by the parent window (main_simplified.py) to access the full application context
        # and handle hardware communication properly

    def _build_display_controls_section(self, tab_layout: QVBoxLayout):
        """Build display controls section (moved from Graphic Control tab)."""
        display_section = CollapsibleSection(
            "🎨 Display Controls",
            is_expanded=False,
        )

        display_help = QLabel(
            "Configure data filtering, reference channels, and visual accessibility",
        )
        display_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        display_section.content_layout.addWidget(display_help)

        # Card container
        display_card = QFrame()
        display_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        display_card_layout = QVBoxLayout(display_card)
        display_card_layout.setContentsMargins(12, 8, 12, 8)
        display_card_layout.setSpacing(12)

        self._build_data_filtering(display_card_layout)
        self._build_reference_section(display_card_layout)
        self._build_visual_accessibility(display_card_layout)

        display_section.add_content_widget(display_card)
        tab_layout.addWidget(display_section)

    def _build_data_filtering(self, layout: QVBoxLayout):
        """Build EMA live display filtering controls section."""
        filter_section = QLabel("Data Filtering")
        filter_section.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(filter_section)
        layout.addSpacing(6)

        # Filter controls layout
        gc_layout = QVBoxLayout()
        gc_layout.setSpacing(8)

        # Description
        desc_label = QLabel(
            "EMA filtering for live display (does not affect saved data):",
        )
        desc_label.setStyleSheet(label_style(11, Colors.SECONDARY_TEXT))
        desc_label.setWordWrap(True)
        gc_layout.addWidget(desc_label)

        # EMA Filter Options
        self.sidebar.filter_method_group = QButtonGroup()

        radio_style = (
            f"QRadioButton {{"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-size: 12px;"
            f"  spacing: 6px;"
            f"}}"
            f"QRadioButton::indicator {{"
            f"  width: 16px;"
            f"  height: 16px;"
            f"  border: 2px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 8px;"
            f"  background: white;"
            f"}}"
            f"QRadioButton::indicator:checked {{"
            f"  background: {Colors.PRIMARY_TEXT};"
            f"  border: 3px solid white;"
            f"  outline: 2px solid {Colors.PRIMARY_TEXT};"
            f"}}"
        )

        # Option 1: None (Raw) - DEFAULT
        self.sidebar.filter_none_radio = QRadioButton("None (Raw) ⭐")
        self.sidebar.filter_none_radio.setChecked(True)  # Default
        self.sidebar.filter_none_radio.setStyleSheet(radio_style)
        self.sidebar.filter_none_radio.setToolTip(
            "No filtering - Raw data display\n"
            "• Baseline noise: ~5.7 RU\n"
            "• Use for: Maximum fidelity, debugging",
        )
        self.sidebar.filter_method_group.addButton(self.sidebar.filter_none_radio, 0)
        gc_layout.addWidget(self.sidebar.filter_none_radio)

        # Option 2: Light Smoothing
        self.sidebar.filter_light_radio = QRadioButton("Light Smoothing")
        self.sidebar.filter_light_radio.setStyleSheet(radio_style)
        self.sidebar.filter_light_radio.setToolTip(
            "Light smoothing filter - Reduces noise while maintaining fast response\n"
            "• Minimal lag during sharp changes\n"
            "• May round fast changes slightly\n"
            "• Use for: General data smoothing, reducing baseline noise",
        )
        self.sidebar.filter_method_group.addButton(self.sidebar.filter_light_radio, 1)
        gc_layout.addWidget(self.sidebar.filter_light_radio)

        # Info note
        info_label = QLabel(
            "💡 Smoothing is applied point-by-point to the live display only. "
            "Saved data remains unfiltered. Applied after peak finding.",
        )
        info_label.setStyleSheet(
            f"color: {Colors.SECONDARY_TEXT};"
            f"font-size: 10px;"
            f"font-style: italic;"
            f"padding: 8px;"
            f"background: {Colors.OVERLAY_LIGHT_4};"
            f"border-radius: 4px;",
        )
        info_label.setWordWrap(True)
        gc_layout.addWidget(info_label)

        layout.addLayout(gc_layout)
        layout.addSpacing(12)

    def _build_reference_section(self, layout: QVBoxLayout):
        """Build reference channel selection section."""
        ref_section = QLabel("Reference Channel")
        ref_section.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(ref_section)
        layout.addSpacing(6)

        # Reference controls
        ref_layout = QVBoxLayout()
        ref_layout.setSpacing(8)

        ref_row = QHBoxLayout()
        ref_row.setSpacing(10)
        ref_label = QLabel("Reference:")
        ref_label.setStyleSheet(
            label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 500;",
        )
        ref_row.addWidget(ref_label)
        ref_row.addStretch()

        self.sidebar.ref_combo = QComboBox()
        self.sidebar.ref_combo.addItems(
            ["None", "Channel A", "Channel B", "Channel C", "Channel D"],
        )
        self.sidebar.ref_combo.setFixedWidth(120)
        self.sidebar.ref_combo.setToolTip(
            "Subtract selected channel from all others (shown as dashed line)",
        )
        self.sidebar.ref_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 6px;"
            f"  padding: 4px 8px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QComboBox:hover {{"
            f"  border: 1px solid rgba(0, 0, 0, 0.15);"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border: none;"
            f"  width: 20px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: white;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  selection-background-color: {Colors.PRIMARY_TEXT};"
            f"  selection-color: white;"
            f"  outline: none;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"}}",
        )
        ref_row.addWidget(self.sidebar.ref_combo)
        ref_layout.addLayout(ref_row)

        # NOTE: Connection is made in affilabs_core_ui.py after app is initialized
        # self.sidebar.ref_combo.currentTextChanged.connect(self.app._on_reference_changed)

        layout.addLayout(ref_layout)
        layout.addSpacing(12)

    def _build_visual_accessibility(self, layout: QVBoxLayout):
        """Build visual accessibility section (colorblind palette)."""
        accessibility_section = QLabel("Visual Accessibility")
        accessibility_section.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(accessibility_section)
        layout.addSpacing(6)

        # Accessibility controls
        accessibility_card_layout = QVBoxLayout()
        accessibility_card_layout.setSpacing(8)

        # Colorblind-friendly palette toggle
        self.sidebar.colorblind_check = QCheckBox(
            "Enable colour-blind friendly palette",
        )
        self.sidebar.colorblind_check.setStyleSheet(checkbox_style())
        self.sidebar.colorblind_check.setToolTip(
            "Use optimized colors for deuteranopia and protanopia (affects all channels)",
        )
        accessibility_card_layout.addWidget(self.sidebar.colorblind_check)

        # Info text about colorblind palette
        colorblind_info = QLabel(
            "Uses optimized colors for deuteranopia and protanopia",
        )
        colorblind_info.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic;",
        )
        accessibility_card_layout.addWidget(colorblind_info)

        # Colorblind palette toggle logic
        def _toggle_colorblind(checked: bool):
            from affilabs.utils.logger import logger
            palette = (
                COLORBLIND_PALETTE
                if checked
                else ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"]
            )
            logger.info(f"Colorblind palette {'enabled' if checked else 'disabled'}")
            # Store the palette choice in sidebar for access by graph updates
            self.sidebar.current_color_palette = palette

            # Save colorblind mode preference for current user
            if hasattr(self.sidebar, 'user_combo'):
                current_user = self.sidebar.user_combo.currentText()
                if current_user and current_user != "Select User...":
                    # Use shared user manager if available
                    if self.user_manager:
                        self.user_manager.set_colorblind_mode(current_user, checked)
                    else:
                        # Fallback
                        from affilabs.services.user_profile_manager import UserProfileManager
                        profile_manager = UserProfileManager()
                        profile_manager.set_colorblind_mode(current_user, checked)

            # Trigger a redraw of the cycle of interest graph if it exists
            if hasattr(self.sidebar, 'app') and hasattr(self.sidebar.app, 'main_window'):
                # Refresh the graph with new colors
                if hasattr(self.sidebar.app, '_update_cycle_of_interest_graph'):
                    try:
                        self.sidebar.app._update_cycle_of_interest_graph()
                    except Exception as e:
                        logger.warning(f"Could not update graph colors: {e}")

        self.sidebar.colorblind_check.toggled.connect(_toggle_colorblind)
        # Initialize default palette
        self.sidebar.current_color_palette = ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"]

        layout.addLayout(accessibility_card_layout)

    def _add_calibration_option(
        self,
        layout: QVBoxLayout,
        title: str,
        description: str,
        button_text: str,
        button_ref: str,
        primary: bool = False,
    ):
        """Add a calibration option with title, description, and button.

        Args:
            layout: Layout to add to
            title: Calibration title
            description: Calibration description
            button_text: Button label text
            button_ref: Attribute name on sidebar to store button reference
            primary: Whether to use primary (dark) button style

        """
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        layout.addWidget(desc_label)

        # Button
        button = QPushButton(button_text)
        button.setFixedHeight(36)

        if primary:
            button.setStyleSheet(
                "QPushButton {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #3A3A3C;"
                "}"
                "QPushButton:pressed {"
                "  background: #48484A;"
                "}",
            )
        else:
            button.setStyleSheet(
                "QPushButton {"
                "  background: white;"
                "  color: #1D1D1F;"
                "  border: 1px solid rgba(0, 0, 0, 0.1);"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.06);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}",
            )

        # Store button reference on sidebar
        setattr(self.sidebar, button_ref, button)
        layout.addWidget(button)

    # Device config sync methods

    def _on_s_position_changed(self, text: str):
        """Sync S position changes to device_config in memory.

        Args:
            text: New S position value from input field

        """
        try:
            if text.strip() and hasattr(self.sidebar, "device_config"):
                s_pos = int(text)
                if 0 <= s_pos <= 255:
                    device_config = self.sidebar.device_config
                    if device_config and hasattr(device_config, "config"):
                        if "hardware" not in device_config.config:
                            device_config.config["hardware"] = {}
                        device_config.config["hardware"]["servo_s_position"] = s_pos
        except (ValueError, AttributeError):
            pass  # Ignore invalid input or missing config

    def _on_p_position_changed(self, text: str):
        """Sync P position changes to device_config in memory.

        Args:
            text: New P position value from input field

        """
        try:
            if text.strip() and hasattr(self.sidebar, "device_config"):
                p_pos = int(text)
                if 0 <= p_pos <= 255:
                    device_config = self.sidebar.device_config
                    if device_config and hasattr(device_config, "config"):
                        if "hardware" not in device_config.config:
                            device_config.config["hardware"] = {}
                        device_config.config["hardware"]["servo_p_position"] = p_pos
        except (ValueError, AttributeError):
            pass  # Ignore invalid input or missing config

    # Helper methods for consistent styling

    def _add_separator(self, layout: QVBoxLayout):
        """Add a horizontal separator line."""
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);border: none;margin: 4px 0px;",
        )
        layout.addWidget(separator)

    def _small_label_style(self) -> str:
        """Return consistent small label stylesheet."""
        return (
            "QLabel {"
            "  font-size: 12px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )

    def _lineedit_style(self) -> str:
        """Return consistent line edit stylesheet."""
        return (
            "QLineEdit {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
            "}"
            "QLineEdit:focus {"
            "  border: 2px solid #1D1D1F;"
            "  padding: 3px 7px;"
            "}"
        )

    def _toggle_button_style(self, is_left: bool) -> str:
        """Return consistent toggle button stylesheet.

        Args:
            is_left: Whether this is the left button in a group (affects border radius)

        """
        border_radius = (
            "border-top-left-radius: 6px; border-bottom-left-radius: 6px; border-right: none;"
            if is_left
            else "border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
        )

        return (
            "QPushButton {"
            "  background: white;"
            "  color: #86868B;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            f"  {border_radius}"
            "  padding: 4px 16px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
