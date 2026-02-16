"""
Spark AI Sidebar - Narrow collapsible sidebar on the left for Spark assistant.
"""

import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
)
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

logger = logging.getLogger(__name__)


class SparkSidebar(QFrame):
    """Narrow collapsible sidebar for Spark AI assistant on the left side."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SparkSidebar")
        self._spark_loaded = False
        self.spark_widget = None
        self._setup_ui()

    def _setup_ui(self):
        """Initialize the Spark sidebar UI."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 14, 12, 10)
        self.main_layout.setSpacing(8)

        # Header with title
        header = self._create_header()
        self.main_layout.addWidget(header)

        # Spark content (lazy loaded)
        self._build_spark_content()

        # Styling
        self.setStyleSheet(
            """
            QFrame#SparkSidebar {
                background-color: #F5F5F7;
                border-right: 1px solid #E5E5EA;
            }
            QLabel {
                color: #333;
            }
            """
        )

    def _create_header(self) -> QWidget:
        """Create header with Spark title and robot icon."""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Robot icon (properly oriented)
        robot_svg = '''<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="5" y="6" width="14" height="12" rx="2" stroke="currentColor" stroke-width="1.25"/>
            <circle cx="9" cy="10" r="1.5" fill="currentColor"/>
            <circle cx="15" cy="10" r="1.5" fill="currentColor"/>
            <path d="M9 14h6" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/>
            <path d="M3 10v4M21 10v4" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/>
        </svg>'''

        # Create robot icon pixmap
        svg_renderer = QSvgRenderer()
        svg_renderer.load(robot_svg.encode())
        robot_pixmap = QPixmap(20, 20)
        robot_pixmap.fill(Qt.transparent)
        painter = QPainter(robot_pixmap)
        svg_renderer.render(painter)
        painter.end()

        robot_icon_label = QLabel()
        robot_icon_label.setPixmap(robot_pixmap)
        robot_icon_label.setFixedSize(20, 20)
        layout.addWidget(robot_icon_label)

        title = QLabel("SPARK AI assistant")
        title.setFixedHeight(27)
        title.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "letter-spacing: -0.3px;"
        )
        layout.addWidget(title)

        layout.addStretch()

        return header

    def _build_spark_content(self):
        """Build Spark AI content (lazy loaded)."""
        # Placeholder that will be replaced when first shown
        self.placeholder = QLabel("Loading Spark AI…")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet(
            "color: #86868B; font-size: 12px; font-style: italic; background: transparent; padding: 40px 20px;"
        )
        self.main_layout.addWidget(self.placeholder, 1)

    def load_spark_widget(self):
        """Lazy load the actual Spark widget on first use."""
        if self._spark_loaded:
            return

        self._spark_loaded = True

        # Remove placeholder
        if self.placeholder:
            self.placeholder.deleteLater()
            self.placeholder = None

        # Load the real Spark widget
        try:
            from affilabs.widgets.spark_help_widget import SparkHelpWidget
            self.spark_widget = SparkHelpWidget()
            self.main_layout.addWidget(self.spark_widget, 1)
            logger.debug("Spark widget loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Spark widget: {e}")
            error_label = QLabel(f"Failed to load Spark:\n{str(e)}")
            error_label.setStyleSheet("color: #FF3B30; font-size: 11px; padding: 20px;")
            error_label.setWordWrap(True)
            self.main_layout.addWidget(error_label, 1)

