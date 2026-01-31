"""
License Management Dialog
UI for viewing license status, entering license keys, and upgrading.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QMessageBox, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from pathlib import Path
import json

from affilabs.config.license_manager import LicenseManager
from affilabs.config.feature_flags import FeatureTier


class LicenseDialog(QDialog):
    """
    Dialog for license management and feature tier information.
    
    Shows:
    - Current license status
    - Available features
    - Locked features with upgrade prompts
    - License key entry
    """
    
    def __init__(self, license_manager: LicenseManager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager
        self.setWindowTitle("License & Features")
        self.setMinimumSize(700, 600)
        self._setup_ui()
    
    def _setup_ui(self):
        """Create dialog UI."""
        layout = QVBoxLayout(self)
        
        # License status section
        status_group = self._create_status_section()
        layout.addWidget(status_group)
        
        # Features section
        features_group = self._create_features_section()
        layout.addWidget(features_group)
        
        # License key entry section
        key_group = self._create_key_entry_section()
        layout.addWidget(key_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_status_section(self) -> QGroupBox:
        """Create license status display section."""
        group = QGroupBox("License Status")
        layout = QVBoxLayout(group)
        
        # Get license info
        info = self.license_manager.get_license_info()
        
        # Status display
        status_layout = QHBoxLayout()
        
        # Tier badge
        tier_label = QLabel(f"🎫 {info['tier_name']}")
        tier_font = QFont()
        tier_font.setPointSize(16)
        tier_font.setBold(True)
        tier_label.setFont(tier_font)
        
        # Color code by tier
        tier_colors = {
            'Free': '#6c757d',
            'Pro': '#0d6efd',
            'Enterprise': '#198754'
        }
        color = tier_colors.get(info['tier_name'], '#6c757d')
        tier_label.setStyleSheet(f"color: {color}; padding: 10px;")
        
        status_layout.addWidget(tier_label)
        status_layout.addStretch()
        
        layout.addLayout(status_layout)
        
        # License details
        details_text = f"""
        <b>Licensee:</b> {info['licensee']}<br>
        <b>Issued:</b> {info.get('issued_date', 'N/A')}<br>
        <b>Expires:</b> {info['expires']}<br>
        <b>Status:</b> {'✅ Valid' if info['is_valid'] else '❌ Invalid'}
        """
        
        if not info['is_valid'] and info.get('errors'):
            details_text += f"<br><br><b>Errors:</b><br>"
            for error in info['errors']:
                details_text += f"• {error}<br>"
        
        details_label = QLabel(details_text)
        details_label.setWordWrap(True)
        layout.addWidget(details_label)
        
        return group
    
    def _create_features_section(self) -> QGroupBox:
        """Create features comparison table."""
        group = QGroupBox("Features by Tier")
        layout = QVBoxLayout(group)
        
        # Features table
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Feature", "Free", "Pro", "Enterprise"])
        
        # Define features
        features = [
            ("Basic SPR Acquisition", True, True, True),
            ("Excel Export", True, True, True),
            ("Method Manager", True, True, True),
            ("Basic QC Validation", True, True, True),
            ("AnIML Export", False, True, True),
            ("Audit Trail", False, True, True),
            ("Advanced Analytics", False, True, True),
            ("Batch Processing", False, True, True),
            ("SiLA 2.0 Integration", False, False, True),
            ("LIMS Integration", False, False, True),
            ("Electronic Signatures", False, False, True),
            ("21 CFR Part 11 Compliance", False, False, True),
        ]
        
        table.setRowCount(len(features))
        
        for row, (feature, free, pro, enterprise) in enumerate(features):
            # Feature name
            table.setItem(row, 0, QTableWidgetItem(feature))
            
            # Checkmarks
            table.setItem(row, 1, QTableWidgetItem("✅" if free else "❌"))
            table.setItem(row, 2, QTableWidgetItem("✅" if pro else "❌"))
            table.setItem(row, 3, QTableWidgetItem("✅" if enterprise else "❌"))
        
        # Style table
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setMaximumHeight(350)
        
        layout.addWidget(table)
        
        return group
    
    def _create_key_entry_section(self) -> QGroupBox:
        """Create license key entry section."""
        group = QGroupBox("License Management")
        layout = QVBoxLayout(group)
        
        # Instructions
        instructions = QLabel(
            "To upgrade your license, obtain a license file from Affilabs and load it below."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        load_btn = QPushButton("📁 Load License File...")
        load_btn.clicked.connect(self._load_license_file)
        button_layout.addWidget(load_btn)
        
        generate_btn = QPushButton("🔧 Generate Test License...")
        generate_btn.clicked.connect(self._generate_test_license)
        generate_btn.setToolTip("For testing purposes only")
        button_layout.addWidget(generate_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        return group
    
    def _load_license_file(self):
        """Load license file from disk."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select License File",
            "",
            "License Files (*.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # Read license file
            with open(file_path, 'r') as f:
                license_data = json.load(f)
            
            # Save to working directory
            if self.license_manager.save_license(license_data):
                # Reload license
                features = self.license_manager.load_license()
                
                QMessageBox.information(
                    self,
                    "License Loaded",
                    f"License successfully loaded!\n\n"
                    f"Tier: {features.tier_name}\n\n"
                    f"Please restart ezControl for changes to take effect."
                )
                self.accept()
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to save license:\n" + "\n".join(self.license_manager.validation_errors)
                )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load license file:\n{e}"
            )
    
    def _generate_test_license(self):
        """Generate a test license (for development)."""
        from PySide6.QtWidgets import QInputDialog, QComboBox
        
        # Ask for tier
        tier, ok = QInputDialog.getItem(
            self,
            "Generate Test License",
            "Select license tier:",
            ["pro", "enterprise"],
            0,
            False
        )
        
        if not ok:
            return
        
        # Ask for licensee
        licensee, ok = QInputDialog.getText(
            self,
            "Generate Test License",
            "Enter licensee name:",
            text="Test User"
        )
        
        if not ok:
            return
        
        # Generate license
        license_data = self.license_manager.generate_license(
            tier=tier,
            licensee=licensee,
            expiration_days=365  # 1 year
        )
        
        # Save license
        if self.license_manager.save_license(license_data):
            features = self.license_manager.load_license()
            
            QMessageBox.information(
                self,
                "Test License Generated",
                f"Test license created!\n\n"
                f"Tier: {features.tier_name}\n"
                f"Licensee: {licensee}\n"
                f"Expires: 1 year from now\n\n"
                f"⚠️ This is for TESTING ONLY.\n"
                f"Please restart ezControl for changes to take effect."
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Error",
                "Failed to save test license."
            )


class UpgradePromptDialog(QDialog):
    """
    Simple dialog prompting user to upgrade for a locked feature.
    """
    
    def __init__(self, feature_name: str, required_tier: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Upgrade Required - {feature_name}")
        self.setMinimumSize(450, 250)
        self._setup_ui(feature_name, required_tier)
    
    def _setup_ui(self, feature_name: str, required_tier: str):
        """Create dialog UI."""
        layout = QVBoxLayout(self)
        
        # Icon and message
        icon_label = QLabel("🔒")
        icon_font = QFont()
        icon_font.setPointSize(48)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        message = QLabel(
            f"<h3>{feature_name}</h3>"
            f"<p>This feature requires <b>{required_tier.title()}</b> tier or higher.</p>"
            f"<p>Upgrade your license to unlock advanced features.</p>"
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        learn_more_btn = QPushButton("Learn More")
        learn_more_btn.clicked.connect(self._learn_more)
        button_layout.addWidget(learn_more_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _learn_more(self):
        """Open license dialog for more information."""
        from affilabs.config.license_manager import LicenseManager
        license_mgr = LicenseManager()
        license_mgr.load_license()
        
        dialog = LicenseDialog(license_mgr, self)
        dialog.exec()
