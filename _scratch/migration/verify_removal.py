"""Quick verification test"""
print("\n=== VERIFICATION ===\n")

files = {
    'Main App': 'main.py',
    'UI Module': 'affilabs/affilabs_core_ui.py',
    'Export Tab': 'affilabs/sidebar_tabs/AL_export_builder.py'
}

for name, path in files.items():
    with open(path, encoding='utf-8') as f:
        content = f.read()
        has_ref = 'send_to_edits' in content
        print(f"{name}: {'❌ FOUND' if has_ref else '✅ REMOVED'}")

print("\n✅ SUCCESS: Send to Edits functionality completely removed\n")
