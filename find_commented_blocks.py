import re
from pathlib import Path

# Find files with large blocks of commented code
def find_commented_blocks(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_comment_block = False
    comment_start = 0
    comment_blocks = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Check if line is a comment (but not docstring or inline comment)
        if stripped.startswith('#') and not stripped.startswith('###'):
            if not in_comment_block:
                in_comment_block = True
                comment_start = i
        else:
            if in_comment_block:
                block_size = i - comment_start
                if block_size > 10:  # Only report blocks > 10 lines
                    comment_blocks.append((comment_start, i-1, block_size))
                in_comment_block = False

    return comment_blocks

# Search affilabs directory
affilabs_dir = Path('affilabs')
python_files = list(affilabs_dir.rglob('*.py'))

print(f"Searching {len(python_files)} Python files for large commented blocks...")
print()

found_blocks = []
for file_path in python_files:
    try:
        blocks = find_commented_blocks(file_path)
        if blocks:
            found_blocks.append((file_path, blocks))
    except Exception as e:
        pass

if found_blocks:
    print(f"Found {len(found_blocks)} files with large commented blocks:")
    for file_path, blocks in sorted(found_blocks)[:10]:  # Show top 10
        print(f"\n{file_path}:")
        for start, end, size in blocks:
            print(f"  Lines {start}-{end} ({size} lines)")
else:
    print("No large commented blocks found.")
