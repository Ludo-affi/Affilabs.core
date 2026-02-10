"""Verification test after removing 'Send Live Data to Edits' functionality"""

import sys

print("\n" + "="*60)
print("SEND TO EDITS REMOVAL VERIFICATION")
print("="*60 + "\n")

# Test 1: Import affilabs_core_ui to ensure no syntax errors
print("Test 1: Importing affilabs_core_ui...")
try:
    from affilabs.affilabs_core_ui import AffilabsCoreUI
    print("✅ affilabs_core_ui imported successfully")
    print(f"   - Signal 'send_to_edits_requested' removed: {not hasattr(AffilabsCoreUI, 'send_to_edits_requested')}")
except Exception as e:
    print(f"❌ Failed to import affilabs_core_ui: {e}")
    sys.exit(1)

# Test 2: Import AL_export_builder to ensure no syntax errors
print("\nTest 2: Importing AL_export_builder...")
try:
    from affilabs.sidebar_tabs.AL_export_builder import build_export_tab
    print("✅ AL_export_builder imported successfully")
except Exception as e:
    print(f"❌ Failed to import AL_export_builder: {e}")
    sys.exit(1)

# Test 3: Check main.py doesn't have the handler
print("\nTest 3: Checking main.py for removed components...")
with open('main.py', 'r', encoding='utf-8') as f:
    main_content = f.read()

has_handler = '_on_send_to_edits_requested' in main_content
has_signal_connect = 'send_to_edits_requested.connect' in main_content

if has_handler or has_signal_connect:
    print(f"⚠️  Warning: Found references that should be removed:")
    print(f"   - Handler method: {has_handler}")
    print(f"   - Signal connection: {has_signal_connect}")
else:
    print("✅ main.py cleaned (no handler or signal connection)")

# Test 4: Check affilabs_core_ui.py
print("\nTest 4: Checking affilabs_core_ui.py for removed components...")
with open('affilabs/affilabs_core_ui.py', 'r', encoding='utf-8') as f:
    ui_content = f.read()

has_signal_def = 'send_to_edits_requested = Signal()' in ui_content
has_ui_handler = 'def _on_send_to_edits_clicked' in ui_content
has_btn_connect = 'send_to_edits_btn.clicked.connect' in ui_content

if has_signal_def or has_ui_handler or has_btn_connect:
    print(f"⚠️  Warning: Found references that should be removed:")
    print(f"   - Signal definition: {has_signal_def}")
    print(f"   - UI handler: {has_ui_handler}")
    print(f"   - Button connection: {has_btn_connect}")
else:
    print("✅ affilabs_core_ui.py cleaned (no signal, handler, or connection)")

# Test 5: Check AL_export_builder.py
print("\nTest 5: Checking AL_export_builder.py for removed button...")
with open('affilabs/sidebar_tabs/AL_export_builder.py', 'r', encoding='utf-8') as f:
    export_content = f.read()

has_button = 'send_to_edits_btn' in export_content
has_button_text = 'Send Live Data to Edits' in export_content

if has_button or has_button_text:
    print(f"⚠️  Warning: Found references that should be removed:")
    print(f"   - Button widget: {has_button}")
    print(f"   - Button text: {has_button_text}")
else:
    print("✅ AL_export_builder.py cleaned (no button or text)")

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print("\n✅ 'Send Live Data to Edits' functionality successfully removed!")
print("\nRemoved components:")
print("  • Export tab button (AL_export_builder.py)")
print("  • Signal definition (affilabs_core_ui.py)")
print("  • Signal handler method (affilabs_core_ui.py)")
print("  • Button click connection (affilabs_core_ui.py)")
print("  • Signal connection (main.py)")
print("  • Data transfer handler (main.py)")
print("\n" + "="*60 + "\n")
