"""Test script to demonstrate layout customization options.

This shows how to move UI elements between widgets for custom layouts.

Usage examples:
1. Move graph settings to device status: mainwindow.move_graph_settings_to_device_status()
2. Move connect button: mainwindow.move_connect_button_to_device_bottom()
3. Manual manipulation:
   - device_status = mainwindow.get_device_status_widget()
   - settings = mainwindow.get_settings_panel()
"""


def customize_layout_example_1(mainwindow):
    """Example 1: Move Graph Display Settings box to Device Status.
    This consolidates all hardware-related controls in one place.
    """
    print("Moving Graph Display Settings to Device Status...")
    success = mainwindow.move_graph_settings_to_device_status()
    if success:
        print("✓ Graph settings successfully moved!")
    else:
        print("✗ Failed to move graph settings")
    return success


def customize_layout_example_2(mainwindow):
    """Example 2: Move the Connect button to the bottom of Device Status.
    Makes the connect button more prominent.
    """
    print("Moving Connect button to bottom...")
    success = mainwindow.move_connect_button_to_device_bottom()
    if success:
        print("✓ Connect button successfully moved!")
    else:
        print("✗ Failed to move connect button")
    return success


def customize_layout_manual(mainwindow):
    """Example 3: Manual layout manipulation.
    Get direct access to widgets and manipulate them as needed.
    """
    device_status = mainwindow.get_device_status_widget()
    settings_panel = mainwindow.get_settings_panel()

    if not device_status or not settings_panel:
        print("✗ Could not access widgets")
        return False

    print("Access granted to:")
    print(f"  - Device Status Widget: {device_status}")
    print(f"  - Settings Panel: {settings_panel}")

    # Example: Get the graph display group
    graph_group = settings_panel.get_graph_display_group()
    print(f"  - Graph Display Group: {graph_group}")

    # Example: Get the connect button
    connect_btn = device_status.get_connect_button()
    print(f"  - Connect Button: {connect_btn}")

    # Example: Get the main layout
    main_layout = device_status.get_main_layout()
    print(f"  - Device Status Main Layout: {main_layout}")

    return True


# To use these in your main.py, add after UI initialization:
"""
# In main.py or mainwindow.py __init__, after self.sidebar.set_widgets():

# Option 1: Move graph settings to device status
self.move_graph_settings_to_device_status()

# Option 2: Move connect button to bottom
self.move_connect_button_to_device_bottom()

# Option 3: Do both
self.move_graph_settings_to_device_status()
self.move_connect_button_to_device_bottom()
"""
