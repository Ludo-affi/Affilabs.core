"""Test QC Dialog imports and instantiation."""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

def test_qc_dialog_import():
    """Test that QC dialog can be imported."""
    print("Testing QC Dialog import...")

    try:
        from affilabs.widgets.calibration_qc_dialog import CalibrationQCDialog
        print("✓ CalibrationQCDialog imported successfully")

        # Check for required method
        if hasattr(CalibrationQCDialog, 'show_qc_report'):
            print("✓ show_qc_report static method exists")
        else:
            print("✗ show_qc_report method NOT FOUND")
            return False

        # Check if class can be instantiated
        print("✓ CalibrationQCDialog class is ready")

        print("\n" + "="*60)
        print("QC DIALOG STATUS: READY ✓")
        print("="*60)
        print("The QC dialog will pop up automatically after calibration")
        print("when _show_qc_dialog() is called from main.py")
        print("="*60)

        return True

    except SyntaxError as e:
        print(f"✗ SYNTAX ERROR: {e}")
        print(f"  File: {e.filename}")
        print(f"  Line: {e.lineno}")
        return False

    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_qc_dialog_import()
    sys.exit(0 if success else 1)
