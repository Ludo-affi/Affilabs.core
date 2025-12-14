# CRITICAL: Python 3.12 REQUIREMENT

## ⚠️ THIS APPLICATION REQUIRES PYTHON 3.12 ⚠️

This codebase uses Python 3.12 features and type hints that are **NOT compatible** with Python 3.9.

## How to Run the Application (ALWAYS USE THESE METHODS)

### Option 1: Use the Dedicated Launcher (RECOMMENDED)
```cmd
run_app_312.bat
```
or
```powershell
.\run_app_312.ps1
```

These launchers **FORCE** Python 3.12 and will error if the virtual environment is missing.

### Option 2: Manual Terminal (If you must)
```powershell
# Activate Python 3.12 environment FIRST
.\.venv312\Scripts\Activate.ps1

# Set PYTHONPATH
$env:PYTHONPATH = "C:\Users\lucia\OneDrive\Desktop\control-3.2.9"

# Run app
python main\main.py
```

### Option 3: VS Code
1. Open workspace in VS Code
2. Press `Ctrl+Shift+P`
3. Type "Python: Select Interpreter"
4. Choose: `Python 3.12.x ('.venv312': venv)`
5. VS Code will now use Python 3.12 for all terminals and runs

## Why Python 3.12?

The codebase uses these Python 3.12+ features:
- Modern type hints with `|` union operator (e.g., `str | None`)
- `tuple[...]` syntax without importing from `typing`
- `datetime.UTC` (Python 3.11+)
- Other modern typing features

## What Happens if You Use Python 3.9?

You'll get errors like:
```
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
AttributeError: module 'datetime' has no attribute 'UTC'
```

## Setup Python 3.12 Virtual Environment

If `.venv312` doesn't exist, create it:

```cmd
# Create virtual environment with Python 3.12
py -3.12 -m venv .venv312

# Activate it
.\.venv312\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## Verifying You're Using Python 3.12

```cmd
python --version
```
Should output: `Python 3.12.x`

## DO NOT:
- ❌ Run `python main\main.py` without activating .venv312 first
- ❌ Use the old `.venv` environment (it's Python 3.9)
- ❌ Change VS Code settings back to `.venv`
- ❌ Use `py` or `python` from system PATH without virtual environment

## DO:
- ✅ Always use `run_app_312.bat` or `run_app_312.ps1`
- ✅ Activate `.venv312` before running any Python commands
- ✅ Verify Python version with `python --version` before running
- ✅ Keep VS Code settings pointing to `.venv312`

---

**Last Updated:** 2025-10-21
**Python Version Required:** 3.12.x
**Virtual Environment:** `.venv312`
