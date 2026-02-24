"""System Intelligence Status Widget

Displays real-time system health status and active issues in the main UI.

Author: AI Assistant
Date: November 21, 2025
"""

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from affilabs.utils.resource_path import get_affilabs_resource

from affilabs.core.system_intelligence import (
    IssueSeverity,
    SystemState,
    get_system_intelligence,
)
from affilabs.utils.logger import logger


class SystemIntelligenceWidget(QWidget):
    """Compact widget showing system health and issues."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.system_intelligence = get_system_intelligence()

        # UI elements
        self.status_label = None
        self.status_indicator = None
        self.issues_text = None

        self._setup_ui()

        # Update timer (every 5 seconds)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(5000)

        # Initial update
        self._update_display()

    def _setup_ui(self):
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Status indicator row
        status_row = QHBoxLayout()

        # Status dot (colored circle)
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("font-size: 20px; color: gray;")
        status_row.addWidget(self.status_indicator)

        # Status text
        self.status_label = QLabel("System Status: Unknown")
        status_font = QFont()
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        status_row.addWidget(self.status_label)

        status_row.addStretch()

        # Diagnose button
        diagnose_btn = QPushButton("[SEARCH] Diagnose")
        diagnose_btn.setMaximumWidth(100)
        diagnose_btn.clicked.connect(self._on_diagnose_clicked)
        status_row.addWidget(diagnose_btn)

        layout.addLayout(status_row)

        # Issues display (collapsible)
        issues_group = QGroupBox("Active Issues")
        issues_layout = QVBoxLayout()

        self.issues_text = QTextEdit()
        self.issues_text.setReadOnly(True)
        self.issues_text.setMaximumHeight(150)
        self.issues_text.setStyleSheet("background-color: #f0f0f0;")
        issues_layout.addWidget(self.issues_text)

        # Action buttons
        button_row = QHBoxLayout()

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._on_clear_all)
        button_row.addWidget(clear_btn)

        report_btn = QPushButton(" Save Report")
        _chart_svg = get_affilabs_resource("ui/img/chart_icon.svg")
        if _chart_svg.exists():
            report_btn.setIcon(QIcon(str(_chart_svg)))
            report_btn.setIconSize(QSize(14, 14))
        report_btn.clicked.connect(self._on_save_report)
        button_row.addWidget(report_btn)

        button_row.addStretch()

        issues_layout.addLayout(button_row)
        issues_group.setLayout(issues_layout)
        layout.addWidget(issues_group)

    def _update_display(self):
        """Update the display with current system state."""
        state, issues = self.system_intelligence.diagnose_system()

        # Update status indicator
        status_colors = {
            SystemState.HEALTHY: ("#00ff00", "Healthy"),
            SystemState.DEGRADED: ("#ffaa00", "Degraded"),
            SystemState.WARNING: ("#ff6600", "Warning"),
            SystemState.ERROR: ("#ff0000", "Error"),
            SystemState.UNKNOWN: ("#888888", "Unknown"),
        }

        color, status_text = status_colors.get(state, ("#888888", "Unknown"))
        self.status_indicator.setStyleSheet(f"font-size: 20px; color: {color};")
        self.status_label.setText(f"System Status: {status_text}")

        # Update issues display
        if not issues:
            self.issues_text.setHtml("<i>No active issues</i>")
        else:
            html_parts = []
            for i, issue in enumerate(issues):
                # Severity emoji
                severity_emoji = {
                    IssueSeverity.CRITICAL: "🔴",
                    IssueSeverity.ERROR: "🟠",
                    IssueSeverity.WARNING: "🟡",
                    IssueSeverity.INFO: "🔵",
                }
                emoji = severity_emoji.get(issue.severity, "⚪")

                # Format issue
                html_parts.append(
                    f"<p><b>{emoji} {issue.title}</b> "
                    f"(Confidence: {issue.confidence*100:.0f}%)<br>",
                )
                html_parts.append(f"<i>{issue.description}</i><br>")

                # Show top 2 recommended actions
                if issue.recommended_actions:
                    html_parts.append("<b>Actions:</b><br>")
                    for action in issue.recommended_actions[:2]:
                        html_parts.append(f"  • {action}<br>")

                html_parts.append("</p><hr>")

            self.issues_text.setHtml("".join(html_parts))

    def _on_diagnose_clicked(self):
        """Manual diagnosis trigger."""
        logger.info("[SEARCH] Running manual system diagnosis...")
        self._update_display()

        # Show maintenance recommendations
        recommendations = self.system_intelligence.get_maintenance_recommendations()
        if recommendations:
            logger.info(f"📋 {len(recommendations)} maintenance recommendations:")
            for rec in recommendations:
                logger.info(f"  [{rec['priority'].upper()}] {rec['title']}")
        else:
            logger.info("[OK] No maintenance recommendations")

    def _on_clear_all(self):
        """Clear all active issues."""
        self.system_intelligence.clear_all_issues()
        self._update_display()
        logger.info("[OK] All issues cleared")

    def _on_save_report(self):
        """Save diagnostic report."""
        try:
            report_path = self.system_intelligence.save_session_report()
            logger.info(f"📊 Session report saved: {report_path}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
