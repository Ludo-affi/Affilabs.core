"""Analyze main.py for duplicate code patterns."""

import re
from collections import Counter
from pathlib import Path

# Read main.py
main_file = Path('main.py')
if not main_file.exists():
    print('main.py not found')
    exit(1)

content = main_file.read_text(encoding='utf-8')
lines = content.split('\n')

print('=' * 70)
print('DUPLICATE CODE ANALYSIS FOR main.py')
print('=' * 70)
print()

# 1. Check for duplicate methods/functions
function_pattern = r'^\s*(def|async def)\s+(\w+)\s*\('
function_names = []
for i, line in enumerate(lines, 1):
    match = re.match(function_pattern, line)
    if match:
        function_names.append((match.group(2), i))

func_counts = Counter([name for name, _ in function_names])
duplicates = {name: count for name, count in func_counts.items() if count > 1}

print('1. DUPLICATE FUNCTION/METHOD NAMES:')
if duplicates:
    for name, count in duplicates.items():
        print(f'   ❌ {name}: appears {count} times')
        locations = [line_num for func_name, line_num in function_names if func_name == name]
        print(f'      Lines: {locations}')
    print()
else:
    print('   ✓ No duplicate function names')
print()

# 2. Check for repeated code blocks (3+ consecutive identical lines)
print('2. REPEATED CODE BLOCKS (3+ identical consecutive lines):')
block_hashes = Counter()
block_locations = {}

for i in range(len(lines) - 2):
    block = '\n'.join(lines[i:i+3])
    normalized = re.sub(r'\s+', ' ', block.strip())
    if normalized and len(normalized) > 30:  # Skip trivial blocks
        if normalized not in block_locations:
            block_locations[normalized] = []
        block_locations[normalized].append(i + 1)
        block_hashes[normalized] += 1

repeated_blocks = {block: count for block, count in block_hashes.items() if count > 1}
if repeated_blocks:
    print(f'   Found {len(repeated_blocks)} repeated patterns')
    for i, (block, count) in enumerate(sorted(repeated_blocks.items(), 
                                              key=lambda x: x[1], 
                                              reverse=True)[:10], 1):
        print(f'\n   Pattern #{i} (appears {count} times):')
        preview = block[:120].replace('\n', ' ')
        print(f'      "{preview}..."')
        locs = block_locations[block][:5]
        print(f'      First occurrences at lines: {locs}')
else:
    print('   ✓ No significant repeated blocks')
print()

# 3. Check for duplicate imports
print('3. DUPLICATE IMPORTS:')
import_pattern = r'^\s*(import|from)\s+(\S+)'
imports = []
for i, line in enumerate(lines, 1):
    match = re.match(import_pattern, line)
    if match:
        imports.append((match.group(0).strip(), i))

import_counts = Counter([imp for imp, _ in imports])
dup_imports = {imp: count for imp, count in import_counts.items() if count > 1}

if dup_imports:
    print(f'   Found {len(dup_imports)} duplicate imports:')
    for imp, count in list(dup_imports.items())[:10]:
        print(f'   ❌ "{imp}" appears {count} times')
else:
    print('   ✓ No duplicate imports')
print()

# 4. Check for error handling patterns
print('4. ERROR HANDLING PATTERNS:')
try_blocks = [i for i, line in enumerate(lines, 1) if re.match(r'^\s*try:\s*$', line)]
except_blocks = [i for i, line in enumerate(lines, 1) if re.match(r'^\s*except', line)]

print(f'   - Try blocks: {len(try_blocks)}')
print(f'   - Except blocks: {len(except_blocks)}')

# Check for similar exception handling
exception_handlers = []
for i, line in enumerate(lines):
    if 'except' in line:
        # Get the next 2-3 lines to see the handling pattern
        handler = '\n'.join(lines[i:i+3])
        normalized = re.sub(r'\s+', ' ', handler.strip())
        exception_handlers.append(normalized)

handler_counts = Counter(exception_handlers)
dup_handlers = {h: count for h, count in handler_counts.items() if count > 2}

if dup_handlers:
    print(f'\n   Similar exception handlers: {len(dup_handlers)} patterns')
    for i, (handler, count) in enumerate(list(dup_handlers.items())[:5], 1):
        print(f'      {i}. Appears {count} times: "{handler[:80]}..."')
print()

# 5. Check for logging patterns
print('5. LOGGING PATTERNS:')
logging_calls = [line for line in lines if 'logger.' in line or 'logging.' in line]
print(f'   - Total logging statements: {len(logging_calls)}')

# Check for similar logging messages
log_pattern = r'logger\.\w+\([\'"](.+?)[\'"]'
log_messages = []
for line in lines:
    matches = re.findall(log_pattern, line)
    log_messages.extend(matches)

if log_messages:
    msg_counts = Counter(log_messages)
    dup_msgs = {msg: count for msg, count in msg_counts.items() if count > 1}
    if dup_msgs:
        print(f'   - Duplicate log messages: {len(dup_msgs)}')
        for msg, count in list(dup_msgs.items())[:5]:
            print(f'      "{msg[:60]}..." appears {count} times')
print()

# 6. Check for similar conditionals
print('6. DUPLICATE CONDITIONAL PATTERNS:')
if_pattern = r'^\s*if\s+(.+):\s*$'
conditions = []
for i, line in enumerate(lines, 1):
    match = re.match(if_pattern, line)
    if match:
        conditions.append((match.group(1).strip(), i))

condition_counts = Counter([c for c, _ in conditions])
dup_conditions = {c: count for c, count in condition_counts.items() if count > 2}

if dup_conditions:
    print(f'   Found {len(dup_conditions)} repeated conditions:')
    for cond, count in sorted(dup_conditions.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f'   - "if {cond}:" appears {count} times')
else:
    print('   ✓ No significant duplicate conditions')
print()

# 7. Summary
print('=' * 70)
print('SUMMARY')
print('=' * 70)
print(f'Total lines analyzed: {len(lines):,}')
print(f'Total functions/methods: {len(function_names)}')
print(f'Duplicate function names: {len(duplicates)}')
print(f'Repeated code blocks: {len(repeated_blocks)}')
print(f'Duplicate imports: {len(dup_imports)}')
print(f'Duplicate conditions: {len(dup_conditions)}')
print()

if duplicates or len(repeated_blocks) > 10 or dup_imports:
    print('⚠️  ISSUES FOUND - Review recommended')
else:
    print('✓ CODE QUALITY: GOOD - Minimal duplication')
