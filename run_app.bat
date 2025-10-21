@echo off
REM Run the Affinite application with Python 3.12 virtual environment
REM This ensures we always use the correct Python version

echo Starting Affinite SPR System with Python 3.12...
echo ================================================

REM Get the directory where this batch file is located
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

REM FORCE Python 3.12 - Check .venv312 first, fallback to .venv
if exist ".venv312\Scripts\python.exe" (
    echo Using Python 3.12 from .venv312
    set "PYTHON_EXE=.venv312\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    echo WARNING: Using .venv instead of .venv312
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    echo ERROR: No virtual environment found!
    echo Please create .venv312: py -3.12 -m venv .venv312
    pause
    exit /b 1
)

REM Set PYTHONPATH to workspace root
set "PYTHONPATH=%APP_DIR%"

REM Verify Python version
echo.
%PYTHON_EXE% --version
echo.

REM Run with virtual environment Python
%PYTHON_EXE% main\main.py

echo.
echo Application closed.
pause