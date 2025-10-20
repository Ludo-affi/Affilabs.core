# Build Specifications

This directory contains PyInstaller specification files for building standalone executables of the Affilabs SPR Control application.

## Build Specs

### `main.spec` (1.2 KB)
- **Target**: Production release build
- **Platform**: Cross-platform base configuration
- **Output**: Single-file executable
- **Use Case**: Standard distribution

### `dev.spec` (1.1 KB)
- **Target**: Development build
- **Platform**: Debug-enabled configuration
- **Output**: Console + GUI executable
- **Use Case**: Testing and debugging

### `mac.spec` (1.3 KB)
- **Target**: macOS release
- **Platform**: macOS-specific bundle
- **Output**: .app bundle
- **Use Case**: Mac distribution

## Building Executables

### Windows
```powershell
# Install PyInstaller
pip install pyinstaller

# Build production executable
pyinstaller build/main.spec

# Output: dist/affilabs-spr-control.exe
```

### macOS
```bash
# Install PyInstaller
pip install pyinstaller

# Build Mac app bundle
pyinstaller build/mac.spec

# Output: dist/AffilabsSPR.app
```

### Development Build
```powershell
# Build with console for debugging
pyinstaller build/dev.spec

# Output includes console window for logs
```

## Customizing Builds

Edit spec files to customize:
- **Icon**: Change `icon='...'` path
- **Name**: Modify `name='...'` parameter
- **Data Files**: Add to `datas=[...]` list
- **Hidden Imports**: Add to `hiddenimports=[...]`
- **One-File vs Directory**: Toggle `onefile=True/False`

## Dependencies

PyInstaller automatically bundles:
- Python interpreter
- All pip packages
- Application code
- Data files specified in spec

## Build Output

```
dist/
├── affilabs-spr-control.exe  (Windows)
├── AffilabsSPR.app/          (macOS)
└── logs/                     (Runtime logs)
```

## Troubleshooting

**Missing modules**: Add to `hiddenimports` in spec file
**Missing data files**: Add to `datas` list
**Large executable size**: Use `--exclude-module` for unused packages
**Runtime errors**: Test with dev.spec first (shows console errors)

## Version Information

Executable version is read from `version.py`:
```python
__version__ = "0.1.0"
__version_name__ = "The Core"
```

Update `version.py` before building releases.

---

**Affilabs 0.1.0 "The Core"**
Build Specifications - October 2025
