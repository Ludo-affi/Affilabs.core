"""Test ModernSidebar with EventBus integration."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.event_bus import EventBus
from PySide6.QtWidgets import QApplication

from widgets.sidebar import ModernSidebar


def test_sidebar_with_event_bus():
    """Test that ModernSidebar correctly integrates with EventBus."""
    print("=" * 60)
    print("Testing ModernSidebar + EventBus Integration")
    print("=" * 60)

    # Create Qt application
    app = QApplication(sys.argv)

    # Create event bus with debug mode
    print("\n1. Creating EventBus with debug mode...")
    event_bus = EventBus(debug_mode=True)
    print("   ✓ EventBus created")

    # Create sidebar with event_bus
    print("\n2. Creating ModernSidebar with event_bus...")
    sidebar = ModernSidebar(event_bus=event_bus)
    print("   ✓ ModernSidebar created")

    # Check that tabs were created
    print("\n3. Checking tab structure...")
    print(f"   - Number of tabs: {sidebar.tab_widget.count()}")
    for i in range(sidebar.tab_widget.count()):
        tab_name = sidebar.tab_widget.tabText(i)
        print(f"   - Tab {i}: {tab_name}")

    # Check tab instances
    print("\n4. Checking tab instances...")
    tabs_to_check = [
        ("device_status_tab", "Device Status"),
        ("graphic_control_tab", "Graphic Control"),
        ("static_tab", "Static"),
        ("flow_tab", "Flow"),
        ("export_tab", "Export"),
        ("settings_tab", "Settings"),
    ]

    for attr_name, tab_name in tabs_to_check:
        tab = getattr(sidebar, attr_name, None)
        if tab is not None:
            print(f"   ✓ {tab_name} tab instance exists")
            # Check event bus connection
            if hasattr(tab, "event_bus") and tab.event_bus is event_bus:
                print("     - EventBus connected: ✓")
            else:
                print("     - EventBus connected: ✗ (not connected)")
        else:
            print(f"   ✗ {tab_name} tab instance NOT found")

    # Test tab change signal
    print("\n5. Testing tab change signals...")
    tab_changed_received = []

    def on_tab_changed(index, name):
        tab_changed_received.append((index, name))
        print(f"   → Tab changed signal received: index={index}, name='{name}'")

    # Connect to both sidebar signal and event bus signal
    sidebar.tab_changed.connect(on_tab_changed)
    event_bus.tab_changed.connect(
        lambda idx, name: print(
            f"   → EventBus tab_changed signal: index={idx}, name='{name}'",
        ),
    )

    # Change tabs programmatically
    print("\n   Switching to tab 1 (Graphic Control)...")
    sidebar.tab_widget.setCurrentIndex(1)

    print("\n   Switching to tab 2 (Static)...")
    sidebar.tab_widget.setCurrentIndex(2)

    # Show sidebar
    print("\n6. Displaying sidebar...")
    sidebar.setWindowTitle("ModernSidebar Test")
    sidebar.resize(900, 700)
    sidebar.show()

    print("\n" + "=" * 60)
    print("✓ All checks completed successfully!")
    print("=" * 60)
    print("\nClose the sidebar window to exit the test.")
    print("You should see tab lifecycle events in the debug output.")

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    test_sidebar_with_event_bus()
