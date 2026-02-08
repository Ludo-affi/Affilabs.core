"""Standalone test for Data Replay Tab Builder

Run this to test the Data Replay UI without integrating into main app.
Uses simulated SPR data for demonstration.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QScrollArea
from PySide6.QtCore import Qt

# Add parent directory to path for affilabs imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_replay_builder import DataReplayTabBuilder


class TestDataReplayWindow(QMainWindow):
    """Standalone window to test Data Replay tab."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Replay Tab - Standalone Test")
        self.setGeometry(100, 100, 750, 700)
        
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area for tab content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Tab content
        tab_content = QWidget()
        tab_content.setStyleSheet("background: #F8F9FA;")
        tab_layout = QVBoxLayout(tab_content)
        tab_layout.setContentsMargins(12, 12, 12, 12)
        tab_layout.setSpacing(8)
        
        # Build Data Replay tab using builder
        # Pass self as "sidebar" since builder just needs to attach widgets
        self.replay_builder = DataReplayTabBuilder(self)
        self.replay_builder.build(tab_layout)
        
        scroll_area.setWidget(tab_content)
        main_layout.addWidget(scroll_area)


def main():
    """Run standalone Data Replay test."""
    print("=" * 80)
    print("DATA REPLAY TAB - STANDALONE TEST")
    print("=" * 80)
    print()
    print("Features to test:")
    print("  1. Click 'Browse...' to load Excel file")
    print("  2. Try: simulated_data/SPR_simulated_20260206_223239.xlsx")
    print("  3. Test playback controls (play, pause, speed)")
    print("  4. Test cycle navigation (prev/next)")
    print("  5. Test export options (GIF, PNG)")
    print()
    print("=" * 80)
    print()
    
    app = QApplication(sys.argv)
    window = TestDataReplayWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
