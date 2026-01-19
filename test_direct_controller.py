"""Direct test of controller connection - bypassing pyserial port enumeration"""
import sys

print("=" * 70)
print("DIRECT CONTROLLER CONNECTION TEST")
print("=" * 70)

# Import controller classes
try:
    from affilabs.core.hardware_manager import _get_controller_classes, _get_settings
    classes = _get_controller_classes()
    settings = _get_settings()
    print(f"✅ Imported controller classes: {list(classes.keys())}")
except Exception as e:
    print(f"❌ Failed to import: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Try each controller type
controllers_to_try = ["PicoP4SPR", "PicoP4PRO", "PicoEZSPR"]

for ctrl_name in controllers_to_try:
    print(f"\n{'='*70}")
    print(f"TRYING: {ctrl_name}")
    print(f"{'='*70}")

    try:
        # Create instance
        ctrl_class = classes[ctrl_name]
        ctrl = ctrl_class()
        print(f"✅ Created {ctrl_name} instance")

        # Try to open
        print(f"Calling {ctrl_name}.open()...")
        result = ctrl.open()
        print(f"open() returned: {result}")

        if result:
            print(f"\n🎉 SUCCESS! Connected to {ctrl_name}")
            print(f"Controller name: {ctrl.name}")

            # Try to get some info
            try:
                if hasattr(ctrl, '_ser') and ctrl._ser:
                    print(f"Port: {ctrl._ser.port}")
                    print(f"Baudrate: {ctrl._ser.baudrate}")

                # Try ID command
                if hasattr(ctrl, 'get_device_type'):
                    dev_type = ctrl.get_device_type()
                    print(f"Device type: {dev_type}")

            except Exception as e:
                print(f"⚠️  Warning getting info: {e}")

            # Close
            if hasattr(ctrl, 'close'):
                ctrl.close()
                print("Closed connection")

            break  # Found one, stop searching
        else:
            print(f"❌ {ctrl_name}.open() returned False")

    except Exception as e:
        print(f"❌ Exception with {ctrl_name}: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'='*70}")
print("TEST COMPLETE")
print(f"{'='*70}")
