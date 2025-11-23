@echo off
REM ============================================================================
REM ROBUST PYTHON 3.12 LAUNCHER
REM This script FORCES the use of Python 3.12 virtual environment
REM ============================================================================

echo.
echo ========================================
echo   SPR Control App - Python 3.12 ONLY
echo ========================================
echo.

REM Get the directory where this batch file is located
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

REM Check if .venv312 exists
if not exist ".venv312\Scripts\python.exe" (
    echo ERROR: Python 3.12 virtual environment not found!
    echo Expected location: %APP_DIR%.venv312
    echo.
    echo Please create the virtual environment first:
    echo    py -3.12 -m venv .venv312
    echo    .venv312\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Verify Python version
echo Verifying Python 3.12...
.venv312\Scripts\python.exe --version
if errorlevel 1 (
    echo ERROR: Failed to run Python from .venv312
    pause
    exit /b 1
)

REM Set PYTHONPATH to workspace root
set "PYTHONPATH=%APP_DIR%"

echo.
echo Using Python: .venv312\Scripts\python.exe
echo PYTHONPATH: %PYTHONPATH%
echo.
echo Starting application...
echo.

REM Run the application using the SPECIFIC Python 3.12 executable
.venv312\Scripts\python.exe main\main.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo ========================================
    echo   Application exited with error
    echo ========================================
    pause
)
