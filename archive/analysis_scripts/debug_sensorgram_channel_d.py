"""Debug script to check channel 'd' visibility and data in sensorgram."""

import json
from pathlib import Path

print("\n" + "=" * 60)
print("CHANNEL 'D' SENSORGRAM DEBUG")
print("=" * 60 + "\n")

# 1. Check configuration
config_file = Path("generated-files/config.json")
if config_file.exists():
    with open(config_file) as f:
        config = json.load(f)

    print("1. CALIBRATION STATUS:")
    print(f"   Calibrated: {config.get('calibrated', False)}")

    # Check if channel 'd' is calibrated
    led_intensities = config.get("led_intensities", {})
    if "d" in led_intensities:
        print(f"   Channel 'd' LED intensity: {led_intensities['d']}")
    else:
        print("   ⚠️  Channel 'd' NOT in led_intensities!")

    # Check for any channel-specific flags
    for key in config:
        if "d" in str(key).lower():
            print(f"   Config['{key}']: {config[key]}")

    print()
else:
    print("❌ Config file not found!")
    print()

# 2. Check if plots might be hidden
print("2. EXPECTED BEHAVIOR:")
print("   - All 4 checkboxes (A, B, C, D) should be checked by default")
print("   - All 4 plots should be visible by default")
print("   - Checkbox state change triggers display_channel_changed()")
print("   - display_channel_changed() calls plots[ch].setVisible(flag)")
print()

print("3. COMMON ISSUES:")
print("   a) Plot visibility not synchronized with checkbox state on startup")
print("   b) Channel 'd' data contains all NaN values (low signal)")
print("   c) Channel 'd' arrays are empty")
print("   d) Plot rendering skipped when isVisible() returns False")
print()

print("4. VERIFICATION NEEDED:")
print("   To verify what's actually happening, we need to:")
print("   - Add debug logging in widgets/graphs.py SensorgramGraph.update()")
print("   - Check if plots['d'].isVisible() returns True")
print("   - Check if lambda_values['d'] contains real data or NaN")
print("   - Check array lengths match other channels")
print()

print("5. RECOMMENDED FIX:")
print("   Option A: Add initialization in DataWindow.__init__() after setup():")
print("   ```python")
print("   # Initialize plot visibility from checkbox state")
print("   for ch in CH_LIST:")
print("       checkbox = getattr(self.ui, f'segment_{ch.upper()}')")
print("       self.full_segment_view.display_channel_changed(ch, checkbox.isChecked())")
print("       self.SOI_view.display_channel_changed(ch, checkbox.isChecked())")
print("   ```")
print()
print("   Option B: Emit stateChanged signal after UI setup:")
print("   ```python")
print("   # Trigger initial visibility update")
print("   for ch in CH_LIST:")
print("       checkbox = getattr(self.ui, f'segment_{ch.upper()}')")
print("       checkbox.stateChanged.emit(checkbox.checkState())")
print("   ```")
print()

# 3. Check the actual UI file
ui_file = Path("ui/ui_sensorgram.py")
if ui_file.exists():
    with open(ui_file) as f:
        ui_content = f.read()

    print("6. UI CHECKBOX STATES:")
    for ch in ["A", "B", "C", "D"]:
        if f"segment_{ch}" in ui_content:
            if f"segment_{ch}.setChecked(True)" in ui_content:
                print(f"   ✅ segment_{ch} checkbox is checked by default")
            elif f"segment_{ch}.setChecked(False)" in ui_content:
                print(f"   ❌ segment_{ch} checkbox is UNCHECKED by default!")
            else:
                print(f"   ⚠️  segment_{ch} checkbox state not explicitly set")
        else:
            print(f"   ❌ segment_{ch} checkbox NOT FOUND in UI!")
    print()

print("=" * 60)
print("NEXT STEPS:")
print("1. Run the app and check terminal output for 'Skipping hidden channel d'")
print("2. Add temporary debug logging to verify data content")
print("3. Apply one of the recommended fixes above")
print("=" * 60 + "\n")
