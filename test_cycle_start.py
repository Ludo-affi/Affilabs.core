"""Test cycle start functionality - diagnose why timer/blue line not showing."""

import sys
sys.path.insert(0, '.')

# Check if _cycle_timer exists and is configured
print("=" * 70)
print("CYCLE START DIAGNOSTIC")
print("=" * 70)

print("\n1. Checking if _cycle_timer is initialized in Application...")
print("   Location: main.py line ~1078")
print("   Expected: _cycle_timer = QTimer() with timeout→_update_cycle_display")

print("\n2. Checking if _update_cycle_display exists...")
print("   Location: main.py line ~2390")
print("   Should update: Intelligence bar, overlay, warning line")

print("\n3. Checking if cycle_of_interest_graph has update_delta_overlay...")
print("   Location: affilabs/widgets/graphs.py line ~1033")

# Try to import and check
try:
    from affilabs.widgets.graphs import Sensorgram4ChannelWidget
    if hasattr(Sensorgram4ChannelWidget, 'update_delta_overlay'):
        print("   ✓ update_delta_overlay method EXISTS on graph widget")
    else:
        print("   ✗ update_delta_overlay method MISSING")

    import inspect
    sig = inspect.signature(Sensorgram4ChannelWidget.update_delta_overlay)
    print(f"   Signature: {sig}")
except Exception as e:
    print(f"   ✗ Error checking: {e}")

print("\n4. Likely issues:")
print("   a) _cycle_timer not starting (check line ~2207 in main.py)")
print("   b) _update_cycle_display throwing exception (check logs)")
print("   c) graph.update_delta_overlay() failing silently")
print("   d) Intelligence bar not updating (check set_intel_message)")

print("\n5. To diagnose:")
print("   - Add print() in _update_cycle_display to see if it's called")
print("   - Check if _current_cycle is None")
print("   - Check if _cycle_end_time is None")
print("   - Add try/except in update_delta_overlay")

print("\n6. Quick fix to test:")
print("   Add logging at start of _update_cycle_display():")
print("   logger.info(f'UPDATE CYCLE DISPLAY: {self._current_cycle}')")

print("\n=" * 70)
print("RUN APPLICATION AND CLICK 'START RUN' TO TEST")
print("=" * 70)
print("\nExpected behavior:")
print("1. Intelligence bar shows: '⏱ Baseline (Cycle 1/1) - 00:00/XX:XX'")
print("2. Active Cycle graph shows overlay with cycle type and timer")
print("3. Blue progress bar/overlay appears on graph")
print("\nIf none appear → _cycle_timer not starting or _update_cycle_display failing")
