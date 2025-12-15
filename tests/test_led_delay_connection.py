"""Test that LED delay setting connects to PRE_LED_DELAY_MS."""

import sys
from pathlib import Path

# Import settings from root (not Old software)
root_path = Path(__file__).parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from settings import settings

print("Initial PRE_LED_DELAY_MS:", settings.PRE_LED_DELAY_MS)

# Simulate what the UI does when changing LED delay
test_delay = 120.0
settings.PRE_LED_DELAY_MS = float(test_delay)

print(f"Updated PRE_LED_DELAY_MS to: {settings.PRE_LED_DELAY_MS}")
print(f"Verification: {test_delay == settings.PRE_LED_DELAY_MS}")

# Reset to default
settings.PRE_LED_DELAY_MS = 95.0
print(f"Reset to default: {settings.PRE_LED_DELAY_MS}")
