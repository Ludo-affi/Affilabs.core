import re
from pathlib import Path
from collections import defaultdict

# Find duplicate function definitions across files
def extract_functions(file_path):
    """Extract all function names and their signatures from a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match function definitions (not inside strings or comments)
    functions = []
    for match in re.finditer(r'^def (\w+)\((.*?)\):', content, re.MULTILINE):
        func_name = match.group(1)
        # Skip private methods and magic methods
        if not func_name.startswith('_'):
            functions.append(func_name)

    return functions

# Search affilabs directory
affilabs_dir = Path('affilabs')
python_files = [f for f in affilabs_dir.rglob('*.py') if 'test' not in str(f) and '__pycache__' not in str(f)]

print(f"Analyzing {len(python_files)} Python files for duplicate functions...")
print()

# Collect all functions
function_locations = defaultdict(list)
for file_path in python_files:
    try:
        functions = extract_functions(file_path)
        for func in functions:
            function_locations[func].append(str(file_path))
    except Exception:
        pass

# Find duplicates
duplicates = {name: files for name, files in function_locations.items() if len(files) > 1}

if duplicates:
    print(f"Found {len(duplicates)} function names used in multiple files:")
    print()
    for func_name in sorted(duplicates.keys())[:15]:  # Show first 15
        files = duplicates[func_name]
        print(f"{func_name} ({len(files)} files):")
        for f in files[:5]:  # Show up to 5 files
            print(f"  - {f}")
        if len(files) > 5:
            print(f"  ... and {len(files) - 5} more")
        print()
else:
    print("No duplicate function names found across files.")
