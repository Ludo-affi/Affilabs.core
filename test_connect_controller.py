"""Test hardware manager controller scanning to debug P4PRO detection."""
import sys
sys.path.insert(0, r'c:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\Affilabs-core')

import logging

# Enable all logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s :: %(levelname)s :: %(message)s'
)

print("="*80)
print("Testing hardware manager controller scan...")
print("="*80)
print()

from affilabs.core.hardware_manager import HardwareManager

# Create hardware manager (this is what the app does)
hw = HardwareManager()

print()
print("Initial state:")
print(f"  ctrl = {hw.ctrl}")
print(f"  _ctrl_raw = {hw._ctrl_raw}")
print(f"  _ctrl_type = {hw._ctrl_type}")
print()

# Call _connect_controller directly (this is what connect_all does)
print("Calling _connect_controller()...")
print("-"*80)
hw._connect_controller()
print("-"*80)
print()

print("Final state:")
print(f"  ctrl = {hw.ctrl}")
print(f"  _ctrl_raw = {hw._ctrl_raw}")
print(f"  _ctrl_type = {hw._ctrl_type}")

if hw.ctrl is not None:
    print()
    print(f"✅ SUCCESS! Controller detected: {hw._ctrl_type}")
    print(f"   Port: {hw._ctrl_port if hasattr(hw, '_ctrl_port') else 'Unknown'}")
else:
    print()
    print("❌ FAILED! No controller detected")
