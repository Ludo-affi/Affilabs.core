# AffiLabs.core Beta - Hardware & UI System

## 📖 READ FIRST

**Before modifying ANY hardware connection or power button logic:**

👉 **READ:** `README_HARDWARE_BEHAVIOR.md`

This document contains:
- Power button state machine
- Hardware scan behavior
- Device type identification rules
- Connection workflow
- Troubleshooting guide
- What NOT to do

## Quick Links

- **Hardware Connection Reference:** `README_HARDWARE_BEHAVIOR.md`
- **Detailed Fix History:** `docs/`
- **UI Documentation:** `UI_ADAPTER_EXAMPLES.md`

## Key Files

| File | Purpose |
|------|---------|
| `affilabs_core_ui.py` | Main UI window |
| `main_simplified.py` | Application layer |
| `core/hardware_manager.py` | Hardware detection |
| `utils/controller.py` | Controller implementations |
| `ui_adapter.py` | UI abstraction layer |

## Running the Application

```bash
cd "c:\Users\ludol\ezControl-AI\Affilabs.core beta"
python main_simplified.py
```

## Important Notes

⚠️ **Scanning hardware while already connected will NOT disconnect existing hardware**
⚠️ **Power button can be clicked to cancel a scan in progress**
⚠️ **Device type is determined by physically connected hardware only**

See `README_HARDWARE_BEHAVIOR.md` for complete details.
