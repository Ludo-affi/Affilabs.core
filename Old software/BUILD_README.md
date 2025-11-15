# Building ezControl Executable

This guide explains how to package the ezControl Old software into a standalone Windows executable (.exe).

## Quick Start

### Option 1: Using Python Script (Recommended)
1. Open PowerShell in the `Old software` directory
2. Run:
   ```powershell
   ..\.venv312\Scripts\python.exe build_executable.py
   ```

### Option 2: Using Batch File
1. Navigate to the `Old software` directory
2. Double-click `build_exe.bat`

## Requirements

- Python 3.12 (already configured in `.venv312`)
- Windows OS
- Internet connection (for downloading packages)

## Build Process

The build script will:

1. **Install build tools**: PyInstaller and Pillow
2. **Install core dependencies**:
   - pyqtgraph (graphs)
   - pyserial (serial communication)
   - PySide6 (GUI framework)
   - scipy (scientific computing)
   - numpy (numerical arrays)
3. **Attempt to install hardware packages** (optional):
   - pump-controller
   - oceandirect
   - ftd2xx
4. **Clean previous builds**: Remove old dist/ and build/ folders
5. **Build executable**: Use PyInstaller with main.spec configuration

## Output

If successful, the executable will be created at:
```
dist/ezControl v3.4/ezControl.exe
```

The entire `dist/ezControl v3.4/` folder contains:
- `ezControl.exe` - Main application
- All required DLL files and dependencies
- Resource files (images, icons, etc.)

## Deployment

To deploy on another PC:

1. Copy the entire `dist/ezControl v3.4/` folder
2. Paste it anywhere on the target Windows PC
3. Run `ezControl.exe` - no installation needed!

## Troubleshooting

### "pump-controller" or "oceandirect" installation fails
- This is expected if these packages are not publicly available
- The build will continue and the exe will still work
- Hardware functionality may be limited without these packages

### Build fails with "No module named 'XXX'"
- Try manually installing the missing package:
  ```powershell
  ..\.venv312\Scripts\python.exe -m pip install XXX
  ```

### Executable crashes on startup
- Check if all dependencies were installed successfully
- Try running from command line to see error messages:
  ```powershell
  cd "dist/ezControl v3.4"
  .\ezControl.exe
  ```

### Splash screen or icon missing
- Ensure these files exist:
  - `ui/img/affinite-splash.png`
  - `ui/img/affinite2.ico`

## Configuration

The build is configured in `main.spec`:
- Entry point: `main/main.py`
- Application name: ezControl
- Output folder name: `ezControl v3.4`
- Icon: `ui/img/affinite2.ico`
- Splash screen: `ui/img/affinite-splash.png`

## Modifications Made

The packaged version includes all recent modifications:
- ✅ Calibration failure bypass
- ✅ S/P position fixes
- ✅ Injection/regeneration timing optimizations
- ✅ Valve control GUI simplification
- ✅ Channel visibility auto-control
- ✅ Table crash-proofing
- ✅ Grid-free graphs by default
- ✅ Fixed median filter (was using mean)
- ✅ Minimum 10 RU Y-axis range for Cycle of Interest

## Version

Build version: **ezControl v3.4**

---

For questions or issues, check the error output or review the build log.
