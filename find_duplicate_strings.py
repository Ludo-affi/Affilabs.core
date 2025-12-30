import re
from pathlib import Path
from collections import Counter

# Find duplicate string literals that could be constants
def find_duplicate_strings(file_path):
    """Find repeated string literals in a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all string literals (both single and double quoted)
    strings = re.findall(r'["\']([^"\']{10,})["\']', content)

    # Count occurrences
    string_counts = Counter(strings)

    # Return strings that appear 3+ times
    return {s: count for s, count in string_counts.items() if count >= 3}

# Search main files
main_files = [
    'main.py',
    'affilabs/affilabs_core_ui.py',
    'affilabs/core/data_acquisition_manager.py',
]

print("Searching for duplicate string literals (3+ occurrences)...")
print()

all_duplicates = {}
for file_path in main_files:
    try:
        duplicates = find_duplicate_strings(file_path)
        if duplicates:
            all_duplicates[file_path] = duplicates
    except Exception as e:
        pass

if all_duplicates:
    for file_path, duplicates in sorted(all_duplicates.items()):
        print(f"\n{file_path}:")
        for string, count in sorted(duplicates.items(), key=lambda x: -x[1])[:5]:
            # Truncate long strings
            display = string[:60] + "..." if len(string) > 60 else string
            print(f"  {count}x: '{display}'")
else:
    print("No major duplicate strings found.")
