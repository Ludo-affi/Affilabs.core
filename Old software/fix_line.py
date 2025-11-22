with open('main/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove line 419 (0-indexed 418) which has the old spectroscopy reference
if 'spectroscopy.update_data' in lines[418]:
    print(f"Removing line 419: {lines[418].strip()}")
    del lines[418]

    with open('main/main.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("✅ Line removed successfully!")
else:
    print("❌ Line 419 doesn't contain the expected text")
