#!/usr/bin/env python
"""Diagnose power button signal path - which connection is active?"""

print("=" * 80)
print("POWER BUTTON SIGNAL PATH ANALYSIS")
print("=" * 80)

print("""
The power button has TWO POSSIBLE PATHS to trigger hardware connection:

PATH 1 (Main Application):
  main.py line 1570 (in _connect_ui_signals method)
  ┌─────────────────────────────────────────────────────────────┐
  │ self.main_window.power_on_requested.connect(                │
  │     self._on_power_on_requested                             │
  │ )                                                           │
  │                                                             │
  │ This calls: _on_power_on_requested() in main.py line 2704  │
  │   → hardware_mgr.scan_and_connect()                         │
  └─────────────────────────────────────────────────────────────┘

PATH 2 (UI Adapter - UNUSED/DUPLICATE):
  affilabs/ui_adapter.py line 52 (in __init__)
  ┌─────────────────────────────────────────────────────────────┐
  │ self.ui.power_on_requested.connect(                         │
  │     self.power_on_requested.emit  # Re-emits signal         │
  │ )                                                           │
  │                                                             │
  │ This is a FORWARDING PROXY that re-emits the signal, but:   │
  │ - ui_adapter.power_on_requested is probably NOT connected   │
  │ - This path is LIKELY UNUSED                               │
  └─────────────────────────────────────────────────────────────┘

KEY QUESTION:
  Is ui_adapter actually instantiated and connected in the app?

FILES TO CHECK:
  1. main.py - Look for any ui_adapter instantiation or connection
  2. affilabs_core_ui.py - Check if ui_adapter is created
  3. Look for listeners on ui_adapter.power_on_requested
""")

print("\n" + "=" * 80)
print("SEARCHING FOR UI ADAPTER USAGE...")
print("=" * 80 + "\n")

import subprocess

# Search for ui_adapter instantiation
result = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "grep -r 'ui_adapter' --include='*.py' 'c:\\Users\\lucia\\OneDrive\\Desktop\\ezControl 2.0\\Affilabs.core\\test\\ezControl-AI\\' | "
     "grep -E '(UIAdapter|ui_adapter)' | head -20"],
    capture_output=True,
    text=True,
    timeout=10
)

if result.stdout:
    print("UI Adapter References:")
    print(result.stdout)
else:
    print("[INFO] Searching for UIAdapter in code...")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("""
If PATH 2 (ui_adapter) is UNUSED:
  ✓ REMOVE the redundant forwarding signal in ui_adapter.py
  ✓ KEEP PATH 1 (main.py line 1570) - it's the actual handler

If PATH 2 (ui_adapter) IS used somewhere:
  ✓ Check that ui_adapter.power_on_requested IS connected to a handler
  ✓ Remove the duplicate if both are wired

ACTION:
  1. Verify power button click → _on_power_on_requested is called
  2. Check that scan_and_connect() runs and completes
  3. Check that _on_hardware_connected() is called when device found
""")
