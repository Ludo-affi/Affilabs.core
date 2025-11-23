# Building ezControl-AI Executable

## Quick Build

**Option 1: Using the batch file (Easiest)**
```batch
build_exe.bat
```

**Option 2: Using the spec file**
```batch
# Activate virtual environment
..\.venv312\Scripts\activate.bat

# Install PyInstaller
pip install pyinstaller

# Build using spec file
pyinstaller ezControl-AI.spec
```

**Option 3: Using the Python build script**
```batch
# Activate virtual environment
..\.venv312\Scripts\activate.bat

# Run build script
python build_exe.py
```

## Output

The executable will be created in:
- `dist/ezControl-AI.exe` (single file)

## Distribution

To distribute the software:
1. Copy `dist/ezControl-AI.exe` to the target computer
2. No Python installation required on target computer
3. All dependencies are bundled in the executable

## Build Options

### Single File vs Directory
- Current: `--onefile` creates a single .exe file
- Alternative: Remove `--onefile` for faster startup (creates folder with dependencies)

### Console Window
- Current: `--windowed` hides console (GUI only)
- Debug: Remove `--windowed` to show console for debugging

### Icon
- Current: Uses `ui/img/affinite2.ico`
- Change: Update `--icon` parameter in build script or spec file

## Troubleshooting

### Missing imports
Add to `hiddenimports` in spec file:
```python
hiddenimports=['missing_module'],
```

### Missing data files
Add to `datas` in spec file:
```python
datas=[('source_path', 'dest_path')],
```

### Build fails
1. Ensure virtual environment is activated
2. Update PyInstaller: `pip install --upgrade pyinstaller`
3. Clear cache: Add `--clean` flag
4. Check all dependencies are installed: `pip install -r requirements.txt`

## File Size

The executable will be approximately 200-400 MB due to:
- Python interpreter
- PySide6 (Qt framework)
- NumPy/SciPy libraries
- All application code

## Testing

After building:
1. Test the executable on your development machine
2. Test on a clean Windows machine without Python
3. Verify all features work (hardware detection, data processing, etc.)
