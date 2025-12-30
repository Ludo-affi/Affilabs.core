from collections import Counter
import re

with open('affilabs/affilabs_core_ui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

methods = []
for i, line in enumerate(lines):
    if re.search(r'^    def \w+\(', line):
        match = re.search(r'def (\w+)\(', line)
        if match:
            methods.append((i+1, match.group(1)))

counts = Counter([m[1] for m in methods])
duplicates = [(name, count) for name, count in counts.items() if count > 1]

if duplicates:
    print('Duplicate methods found:')
    for name, count in sorted(duplicates):
        print(f'  {name}: {count} definitions')
        # Show line numbers
        lines_with_method = [m[0] for m in methods if m[1] == name]
        print(f'    Lines: {lines_with_method}')
else:
    print('No duplicate methods found!')
