"""Fix restart timer logic"""

with open('affilabs/affilabs_core_ui.py', 'rb') as f:
    data = f.read()

# Find and replace the wrong _show_popout_timer call with set_paused + update_countdown
old = b"        # Re-show pop-out window with restarted timer\n        self._show_popout_timer(label, initial_duration)"
new = b"""        # Update pop-out window and clear paused state
        if hasattr(self, '_popout_timer') and self._popout_timer:
            self._popout_timer.set_paused(False)
            self._popout_timer.update_countdown(label, initial_duration)"""

if old in data:
    data = data.replace(old, new)
    with open('affilabs/affilabs_core_ui.py', 'wb') as f:
        f.write(data)
    print("SUCCESS: Fixed _on_restart_manual_timer")
else:
    print("FAILED: Could not find restart pattern")
    # Try finding the _show_popout_timer portion
    idx = data.find(b'self._show_popout_timer(label, initial_duration)')
    if idx >= 0:
        print("Found _show_popout_timer call at byte offset:", idx)
        print("Context:", repr(data[idx-100:idx+150]))
