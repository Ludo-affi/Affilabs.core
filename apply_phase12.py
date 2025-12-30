"""Apply Phase 12: Clean up debug print statements.

Replace print() with logger.debug() for proper logging infrastructure.
"""
import re

file_path = "affilabs/affilabs_core_ui.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Specific debug prints to remove (these are verbose and not useful in production)
debug_prints_to_remove = [
    'print("DEBUG: enable_start_button() called")\n',
    'print("DEBUG: enable_start_button signal emitted")\n',
    'print("DEBUG: _do_enable_start() executing in main thread")\n',
    'print("DEBUG: Setting _is_complete = True...")\n',
    'print("DEBUG: Enabling start button...")\n',
    'print("DEBUG: Start button enabled")\n',
]

# Error prints to convert to logger.error()
error_prints_to_convert = {
    'print(f"🔴 ERROR: RuntimeError in _do_update_status: {e}")': 'logger.error(f"RuntimeError in _do_update_status: {e}")',
    'print(f"🔴 ERROR: Exception in _do_update_status: {e}")': 'logger.error(f"Exception in _do_update_status: {e}")',
    'print(f"🔴 ERROR: RuntimeError in _do_update_title: {e}")': 'logger.error(f"RuntimeError in _do_update_title: {e}")',
    'print(f"🔴 ERROR: Exception in _do_update_title: {e}")': 'logger.error(f"Exception in _do_update_title: {e}")',
    'print(f"🔴 ERROR: RuntimeError in _do_hide_progress: {e}")': 'logger.error(f"RuntimeError in _do_hide_progress: {e}")',
    'print(f"🔴 ERROR: Exception in _do_hide_progress: {e}")': 'logger.error(f"Exception in _do_hide_progress: {e}")',
    'print(f"🔴 ERROR: RuntimeError in _do_enable_start: {e}")': 'logger.error(f"RuntimeError in _do_enable_start: {e}")',
    'print(f"🔴 ERROR: Exception in _do_enable_start: {e}")': 'logger.error(f"Exception in _do_enable_start: {e}")',
}

# Info prints to convert to logger.debug() or logger.info()
info_prints_to_convert = {
    'print(f"Selected all data: 0s to {stop_time:.1f}s")': 'logger.debug(f"Selected all data: 0s to {stop_time:.1f}s")',
    'print(f"Exporting range: {start_time:.1f}s to {stop_time:.1f}s")': 'logger.debug(f"Exporting range: {start_time:.1f}s to {stop_time:.1f}s")',
    'print("Application not initialized")': 'logger.warning("Application not initialized")',
    'print("Export function not available")': 'logger.warning("Export function not available")',
}

# Exception prints to convert to logger.error()
exception_error_prints = [
    ('print(f"Error selecting time range: {e}")', 'logger.error(f"Error selecting time range: {e}")'),
    ('print(f"Error selecting all data: {e}")', 'logger.error(f"Error selecting all data: {e}")'),
    ('print(f"Error updating start cursor: {e}")', 'logger.error(f"Error updating start cursor: {e}")'),
    ('print(f"Error updating stop cursor: {e}")', 'logger.error(f"Error updating stop cursor: {e}")'),
    ('print(f"Error updating cursor inputs: {e}")', 'logger.error(f"Error updating cursor inputs: {e}")'),
    ('print(f"Error exporting cursor range: {e}")', 'logger.error(f"Error exporting cursor range: {e}")'),
    ('print(f"Error applying snap: {e}")', 'logger.error(f"Error applying snap: {e}")'),
]

removed_count = 0
converted_count = 0

# Process each line
for i, line in enumerate(lines):
    stripped = line.lstrip()

    # Remove debug prints
    if stripped in debug_prints_to_remove:
        lines[i] = ''  # Remove the line
        removed_count += 1
        continue

    # Convert error prints
    for old_print, new_logger in error_prints_to_convert.items():
        if old_print in stripped:
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}{new_logger}\n"
            converted_count += 1
            break

    # Convert info prints
    for old_print, new_logger in info_prints_to_convert.items():
        if old_print in stripped:
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}{new_logger}\n"
            converted_count += 1
            break

    # Convert exception error prints
    for old_print, new_logger in exception_error_prints:
        if old_print in stripped:
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}{new_logger}\n"
            converted_count += 1
            break

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"✓ Phase 12: Debug Print Cleanup")
print(f"  - Removed {removed_count} debug print statements")
print(f"  - Converted {converted_count} prints to logger calls")
print(f"  Total: {removed_count + converted_count} improvements")
